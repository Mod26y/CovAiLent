import logging
from typing import List, Dict, Any

from rdkit import Chem
from rdkit.Chem import AllChem

from tool_schema import MCPTool
from pydantic import BaseModel, Field

# Configure logger for this module
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class MutateLigandInput(BaseModel):
    smiles: str = Field(..., description="Original molecule in SMILES format")
    modification: str = Field(..., description="Textual description of the desired modification")


class MutateLigandOutput(BaseModel):
    modified_smiles: str = Field(..., description="Modified molecule in SMILES format")
    logs: List[str] = Field(..., description="Step-by-step logs of the mutation process")


class MutateLigandTool(MCPTool):
    name = "mutate_ligand"
    description = "Apply a textual chemical modification to a ligand SMILES using RDKit."
    input_schema = MutateLigandInput
    output_schema = MutateLigandOutput

    def run(self, input_data: MutateLigandInput) -> Dict[str, Any]:
        logs: List[str] = []
        try:
            logs.append(f"Parsing input SMILES: {input_data.smiles}")
            mol = Chem.MolFromSmiles(input_data.smiles)
            if mol is None:
                logs.append("Error: could not parse SMILES into RDKit Mol object.")
                return {"modified_smiles": "", "logs": logs}
            logs.append("Successfully parsed SMILES to RDKit Mol.")

            # Placeholder for real modification logic
            logs.append(f"Requested modification: '{input_data.modification}'")
            logs.append("Mutation logic not implemented; returning original molecule.")

            modified_smiles = Chem.MolToSmiles(mol)
            logs.append(f"Resulting SMILES: {modified_smiles}")

            return {"modified_smiles": modified_smiles, "logs": logs}
        except Exception as e:
            errmsg = f"Exception during mutation: {e}"
            logger.exception(errmsg)
            logs.append(errmsg)
            return {"modified_smiles": "", "logs": logs}


class OptimizeMoleculeInput(BaseModel):
    smiles: str = Field(..., description="Molecule in SMILES format to optimize")
    max_iterations: int = Field(200, description="Maximum iterations for force field optimization")


class OptimizeMoleculeOutput(BaseModel):
    optimized_smiles: str = Field(..., description="SMILES of the optimized molecule (connectivity unchanged)")
    energy: float = Field(..., description="Final force-field energy after optimization")
    logs: List[str] = Field(..., description="Step-by-step logs of the optimization process")


class OptimizeMoleculeTool(MCPTool):
    name = "optimize_molecule"
    description = "Generate a 3D conformation and optimize it using UFF/MMFF via RDKit."
    input_schema = OptimizeMoleculeInput
    output_schema = OptimizeMoleculeOutput

    def run(self, input_data: OptimizeMoleculeInput) -> Dict[str, Any]:
        logs: List[str] = []
        try:
            logs.append(f"Parsing input SMILES: {input_data.smiles}")
            mol = Chem.MolFromSmiles(input_data.smiles)
            if mol is None:
                logs.append("Error: invalid SMILES, cannot parse.")
                return {"optimized_smiles": "", "energy": 0.0, "logs": logs}
            logs.append("Parsed SMILES into Mol object.")

            # Add hydrogens and embed 3D coordinates
            mol_h = Chem.AddHs(mol)
            logs.append("Added explicit hydrogens.")

            embed_status = AllChem.EmbedMolecule(mol_h)
            if embed_status != 0:
                logs.append(f"Warning: embedding returned status {embed_status}.")
            else:
                logs.append("3D coordinates successfully embedded.")

            # Optimize with UFF, fallback to MMFF
            try:
                ff = AllChem.UFFGetMoleculeForceField(mol_h)
                logs.append("Using UFF force field.")
            except Exception:
                ff = AllChem.MMFFOptimizeMolecule(mol_h, maxIters=input_data.max_iterations)
                logs.append("Using MMFF as fallback.")

            if hasattr(ff, 'CalcEnergy'):
                ff.Minimize(maxIts=input_data.max_iterations)
                energy = ff.CalcEnergy()
                logs.append("Force field minimization complete.")
            else:
                # In case ff is an int from MMFFOptimizeMolecule
                energy = float(ff)
                logs.append("Force field minimization complete (MMFF).")

            optimized_smiles = Chem.MolToSmiles(Chem.RemoveHs(mol_h))
            logs.append(f"Optimized molecule SMILES: {optimized_smiles}")
            logs.append(f"Final energy: {energy}")

            return {"optimized_smiles": optimized_smiles, "energy": energy, "logs": logs}
        except Exception as e:
            errmsg = f"Exception during optimization: {e}"
            logger.exception(errmsg)
            return {"optimized_smiles": "", "energy": 0.0, "logs": [errmsg]}
