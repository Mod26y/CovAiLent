import logging
from typing import List, Dict, Any, Optional

import requests
from pydantic import BaseModel, Field, validator

from tool_schema import MCPTool

# Configure module logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

CHEMBL_BASE_URL = "https://www.ebi.ac.uk/chembl/api/data"


class FetchCompoundByNameInput(BaseModel):
    name: str = Field(..., description="Preferred compound name or synonym.")


class FetchCompoundByNameOutput(BaseModel):
    chembl_id: Optional[str] = Field(None, description="ChEMBL compound identifier.")
    name: Optional[str] = Field(None, description="Matched compound name.")
    smiles: Optional[str] = Field(None, description="Canonical SMILES string.")
    molecular_formula: Optional[str] = Field(None, description="Molecular formula.")
    molecular_weight: Optional[float] = Field(None, description="Molecular weight.")
    logs: List[str] = Field(..., description="Logs detailing the fetch process.")


class FetchCompoundByNameTool(MCPTool):
    name = "fetch_compound_by_name"
    description = "Retrieve compound metadata from ChEMBL by compound name."
    input_schema = FetchCompoundByNameInput
    output_schema = FetchCompoundByNameOutput

    def run(self, input_data: FetchCompoundByNameInput) -> Dict[str, Any]:
        logs: List[str] = []
        try:
            search_url = f"{CHEMBL_BASE_URL}/molecule/search/{input_data.name}.json?limit=1"
            logs.append(f"Querying ChEMBL molecule search endpoint: {search_url}")
            response = requests.get(search_url, timeout=10)

            if response.status_code == 404:
                logs.append(f"No compound found for name: {input_data.name} (404).")
                return {**{}, 'logs': logs}
            if response.status_code == 429:
                logs.append("Rate limit exceeded when querying compound by name.")
                return {**{}, 'logs': logs}

            response.raise_for_status()
            data = response.json()
            molecules = data.get('molecules') or data.get('molecule') or []
            if not molecules:
                logs.append(f"No results returned for name: {input_data.name}.")
                return {**{}, 'logs': logs}

            mol = molecules[0]
            logs.append(f"Found compound: {mol.get('molecule_chembl_id')} ({mol.get('pref_name')}).")

            output = {
                'chembl_id': mol.get('molecule_chembl_id'),
                'name': mol.get('pref_name'),
                'smiles': mol.get('canonical_smiles'),
                'molecular_formula': mol.get('molecular_formula'),
                'molecular_weight': float(mol.get('molecular_weight') or 0.0),
                'logs': logs
            }
            return output

        except requests.exceptions.RequestException as e:
            errmsg = f"HTTP error during ChEMBL fetch: {e}"
            logger.exception(errmsg)
            logs.append(errmsg)
            return {**{}, 'logs': logs}
        except Exception as e:
            errmsg = f"Unexpected error in fetch_compound_by_name: {e}"
            logger.exception(errmsg)
            logs.append(errmsg)
            return {**{}, 'logs': logs}


class GetActivityDataForTargetInput(BaseModel):
    uniprot_id: str = Field(..., description="UniProt accession for target protein.")


class ActivityRecord(BaseModel):
    compound_chembl_id: str = Field(..., description="ChEMBL compound ID.")
    standard_type: Optional[str] = Field(None, description="Assayed measurement type (e.g., IC50).")
    standard_value: Optional[float] = Field(None, description="Measured value.")
    standard_units: Optional[str] = Field(None, description="Units of measurement.")
    pchembl_value: Optional[float] = Field(None, description="-log(Molar) activity value.")


class GetActivityDataForTargetOutput(BaseModel):
    target_chembl_id: Optional[str] = Field(None, description="ChEMBL target ID.")
    activities: List[ActivityRecord] = Field(..., description="List of activity records.")
    logs: List[str] = Field(..., description="Logs detailing the activity fetch process.")


class GetActivityDataForTargetTool(MCPTool):
    name = "get_activity_data_for_target"
    description = "Fetch bioactivity data from ChEMBL for a given UniProt ID."
    input_schema = GetActivityDataForTargetInput
    output_schema = GetActivityDataForTargetOutput

    def run(self, input_data: GetActivityDataForTargetInput) -> Dict[str, Any]:
        logs: List[str] = []
        try:
            # Step 1: map UniProt ID to target_chembl_id
            target_search = f"{CHEMBL_BASE_URL}/target/search/{input_data.uniprot_id}.json?limit=1"
            logs.append(f"Querying ChEMBL target search endpoint: {target_search}")
            resp_t = requests.get(target_search, timeout=10)
            if resp_t.status_code == 404:
                logs.append(f"No target found for UniProt ID: {input_data.uniprot_id} (404).")
                return {'activities': [], 'logs': logs}
            if resp_t.status_code == 429:
                logs.append("Rate limit exceeded when querying target.")
                return {'activities': [], 'logs': logs}
            resp_t.raise_for_status()
            target_data = resp_t.json().get('targets') or []
            if not target_data:
                logs.append(f"No targets returned for UniProt ID: {input_data.uniprot_id}.")
                return {'activities': [], 'logs': logs}
            target_chembl = target_data[0].get('target_chembl_id')
            logs.append(f"Mapped UniProt {input_data.uniprot_id} to ChEMBL target {target_chembl}.")

            # Step 2: fetch activities for this target
            activity_url = f"{CHEMBL_BASE_URL}/activity.json?target_chembl_id={target_chembl}&limit=50"
            logs.append(f"Querying ChEMBL activity endpoint: {activity_url}")
            resp_a = requests.get(activity_url, timeout=10)
            if resp_a.status_code == 404:
                logs.append(f"No activity data for target {target_chembl} (404).")
                return {'target_chembl_id': target_chembl, 'activities': [], 'logs': logs}
            if resp_a.status_code == 429:
                logs.append("Rate limit exceeded when querying activities.")
                return {'target_chembl_id': target_chembl, 'activities': [], 'logs': logs}
            resp_a.raise_for_status()
            act_data = resp_a.json().get('activities') or []

            activities: List[Dict[str, Any]] = []
            for rec in act_data:
                activities.append({
                    'compound_chembl_id': rec.get('molecule_chembl_id'),
                    'standard_type': rec.get('standard_type'),
                    'standard_value': rec.get('standard_value'),
                    'standard_units': rec.get('standard_units'),
                    'pchembl_value': rec.get('pchembl_value')
                })
            logs.append(f"Retrieved {len(activities)} activity records for target {target_chembl}.")

            return {'target_chembl_id': target_chembl, 'activities': activities, 'logs': logs}

        except requests.exceptions.RequestException as e:
            errmsg = f"HTTP error during activity fetch: {e}"
            logger.exception(errmsg)
            logs.append(errmsg)
            return {'activities': [], 'logs': logs}
        except Exception as e:
            errmsg = f"Unexpected error in get_activity_data_for_target: {e}"
            logger.exception(errmsg)
            logs.append(errmsg)
            return {'activities': [], 'logs': logs}
