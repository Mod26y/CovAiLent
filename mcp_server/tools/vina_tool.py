import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any, List

from pydantic import BaseModel, Field, validator

from tool_schema import MCPTool

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


class DockLigandInput(BaseModel):
    ligand_smiles: str = Field(..., description="Ligand structure in SMILES format")
    receptor_pdb_path: str = Field(..., description="Path to the target protein PDB file")
    center_x: float = Field(None, description="X coordinate of docking box center")
    center_y: float = Field(None, description="Y coordinate of docking box center")
    center_z: float = Field(None, description="Z coordinate of docking box center")
    size_x: float = Field(20.0, description="Size of docking box along X axis")
    size_y: float = Field(20.0, description="Size of docking box along Y axis")
    size_z: float = Field(20.0, description="Size of docking box along Z axis")
    exhaustiveness: int = Field(8, description="Exhaustiveness of the global search (higher is slower)")
    num_modes: int = Field(9, description="Maximum number of binding modes to generate")

    @validator('receptor_pdb_path')
    def check_receptor_exists(cls, v: str) -> str:
        if not Path(v).exists():
            raise ValueError(f"Receptor file not found: {v}")
        return v


class DockLigandOutput(BaseModel):
    top_score: float = Field(..., description="Best docking affinity score (kcal/mol)")
    pose_output_path: str = Field(..., description="Path to the PDBQT file of the top-scoring pose")
    logs: List[str] = Field(..., description="Step-by-step execution logs for LLMs")


class DockLigandTool(MCPTool):
    name = "dock_ligand"
    description = "Dock a ligand into a protein using AutoDock Vina via command line."
    input_schema = DockLigandInput
    output_schema = DockLigandOutput

    def run(self, input_data: DockLigandInput) -> Dict[str, Any]:
        logs: List[str] = []
        try:
            # Prepare temporary working directory
            workdir = Path(tempfile.mkdtemp(prefix="vina_"))
            logs.append(f"Created working directory: {workdir}")

            # Prepare receptor: convert PDB to PDBQT
            receptor_pdb = Path(input_data.receptor_pdb_path)
            receptor_pdbqt = workdir / (receptor_pdb.stem + ".pdbqt")
            cmd_prep_rec = [
                "prepare_receptor", "-r", str(receptor_pdb), "-o", str(receptor_pdbqt)
            ]
            logs.append(f"Running receptor preparation: {' '.join(cmd_prep_rec)}")
            subprocess.run(cmd_prep_rec, check=True, capture_output=True)
            logs.append("Receptor PDBQT generated.")

            # Prepare ligand: SMILES -> PDBQT
            ligand_pdbqt = workdir / "ligand.pdbqt"
            cmd_prep_lig = [
                "prepare_ligand4", "-l", "-", "-o", str(ligand_pdbqt)
            ]
            logs.append(f"Running ligand preparation: {' '.join(cmd_prep_lig)}")
            # feed SMILES via stdin
            proc = subprocess.run(
                cmd_prep_lig,
                input=input_data.ligand_smiles.encode(),
                check=True,
                capture_output=True
            )
            logs.append("Ligand PDBQT generated.")

            # Build Vina command
            out_poses = workdir / "out.pdbqt"
            vina_cmd = [
                "vina",
                "--receptor", str(receptor_pdbqt),
                "--ligand", str(ligand_pdbqt),
                "--center_x", str(input_data.center_x or 0.0),
                "--center_y", str(input_data.center_y or 0.0),
                "--center_z", str(input_data.center_z or 0.0),
                "--size_x", str(input_data.size_x),
                "--size_y", str(input_data.size_y),
                "--size_z", str(input_data.size_z),
                "--exhaustiveness", str(input_data.exhaustiveness),
                "--num_modes", str(input_data.num_modes),
                "--out", str(out_poses)
            ]
            logs.append(f"Executing Vina: {' '.join(vina_cmd)}")
            result = subprocess.run(vina_cmd, check=True, capture_output=True, text=True)
            logs.extend(result.stdout.splitlines())

            # Parse top score from stdout
            top_score = None
            for line in result.stdout.splitlines():
                if line.strip().startswith("1 "):
                    parts = line.split()
                    try:
                        top_score = float(parts[1])
                        logs.append(f"Parsed top score: {top_score}")
                    except Exception:
                        logs.append(f"Failed to parse score line: {line}")
                    break
            if top_score is None:
                logs.append("No docking score parsed; setting top_score to 0.0")
                top_score = 0.0

            return {
                "top_score": top_score,
                "pose_output_path": str(out_poses),
                "logs": logs
            }

        except subprocess.CalledProcessError as cpe:
            err = cpe.stderr.decode() if cpe.stderr else str(cpe)
            errmsg = f"Subprocess failed: {err}"
            logger.exception(errmsg)
            logs.append(errmsg)
            return {"top_score": 0.0, "pose_output_path": "", "logs": logs}
        except Exception as e:
            errmsg = f"Exception during docking: {e}"
            logger.exception(errmsg)
            logs.append(errmsg)
            return {"top_score": 0.0, "pose_output_path": "", "logs": logs}
