# Sample LLM Interaction: Ligand Design for JAK2

Below is an example transcript of an LLM-driven session using the CovAIlent MCP server to design and analyze a JAK2 inhibitor.

---

**LLM**: Let’s start by fetching a known JAK2 inhibitor from ChEMBL. We’ll search for **ruxolitinib**.

```bash
# Tool call: fetch_compound_by_name
POST /tools/fetch_compound_by_name/run
{
  "name": "ruxolitinib"
}
```

**Tool Response**:
```json
{
  "chembl_id": "CHEMBL4335",
  "name": "Ruxolitinib",
  "smiles": "CC1=C(C=C(C=C1)C)C(=O)N2CCC(CC2)N3C=NC=N3",
  "molecular_formula": "C17H18N6O",
  "molecular_weight": 306.36,
  "logs": [
    "Querying ChEMBL molecule search endpoint: https://www.ebi.ac.uk/chembl/api/data/molecule/search/ruxolitinib.json",
    "Found compound: CHEMBL4335 (Ruxolitinib)."
  ]
}
```

**LLM**: Great. Next, let’s introduce a methyl group at the para position of the phenyl ring to explore potential potency gains.

```bash
# Tool call: mutate_ligand
POST /tools/mutate_ligand/run
{
  "smiles": "CC1=C(C=C(C=C1)C)C(=O)N2CCC(CC2)N3C=NC=N3",
  "modification": "add methyl group to para position"
}
```

**Tool Response**:
```json
{
  "modified_smiles": "CC1=C(C=C(C=C1)(C)C)C(=O)N2CCC(CC2)N3C=NC=N3",
  "logs": [
    "Parsing input SMILES: CC1=C(C=C(C=C1)C)C(=O)N2CCC(CC2)N3C=NC=N3",
    "Requested modification: 'add methyl group to para position'",
    "Applied SMARTS transform: added methyl at carbon 4",
    "Resulting SMILES: CC1=C(C=C(C=C1)(C)C)C(=O)N2CCC(CC2)N3C=NC=N3"
  ]
}
```

**LLM**: The modification looks correct. Let’s dock the modified ligand into the JAK2 structure.

```bash
# Tool call: dock_ligand
POST /tools/dock_ligand/run
{
  "ligand_smiles": "CC1=C(C=C(C=C1)(C)C)C(=O)N2CCC(CC2)N3C=NC=N3",
  "receptor_pdb_path": "/data/jak2.pdb"
}
```

**Tool Response**:
```json
{
  "top_score": -9.5,
  "pose_pdbqt_path": "/tmp/jak2_ligand_best.pdbqt",
  "logs": [
    "Preparing receptor file: /data/jak2.pdb -> /tmp/receptor.pdbqt",
    "Preparing ligand PDBQT from SMILES",
    "Running Vina [-box 20,20,20 at center (10,10,10)]",
    "Docking complete; best score: -9.5"
  ]
}
```

**LLM**: Promising docking score. Finally, let’s visualize the binding mode with PyMOL.

```bash
# Tool call: visualize_binding
POST /tools/visualize_binding/run
{
  "receptor_pdb_path": "/data/jak2.pdb",
  "ligand_pose_path": "/tmp/jak2_ligand_best.pdbqt"
}
```

**Tool Response**:
```json
{
  "image_path": "/tmp/jak2_binding_mode.png",
  "logs": [
    "Loaded receptor in PyMOL",
    "Loaded ligand pose",
    "Applied coloring and rendering settings",
    "Exported image to /tmp/jak2_binding_mode.png"
  ]
}
```

**LLM**: Here is the binding mode image:

![](/tmp/jak2_binding_mode.png)

---

This sample session demonstrates chaining of MCP tools—**fetch_compound_by_name**, **mutate_ligand**, **dock_ligand**, and **visualize_binding**—to design and evaluate a JAK2 ligand in an autonomous, LLM-driven workflow.  

