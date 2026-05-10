import os
import uuid
import json
import shutil
from pathlib import Path
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv

# Ensure we import from the local modules
from orchestrator.agent import HermesOrchestrator

load_dotenv()

app = FastAPI(title="MiMo Hermes Web Demo")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def read_index():
    return FileResponse("static/index.html")

@app.get("/style.css")
def read_css():
    return FileResponse("static/style.css")

@app.get("/script.js")
def read_js():
    return FileResponse("static/script.js")

class AnalyzeRequest(BaseModel):
    repo_url: str

@app.post("/api/analyze")
def analyze_repo(req: AnalyzeRequest):
    run_id = str(uuid.uuid4())
    workspace = Path(f"./workspace/{run_id}")
    workspace.mkdir(parents=True, exist_ok=True)
    
    try:
        orchestrator = HermesOrchestrator(
            source_repo=req.repo_url,
            workspace_dir=workspace,
            model="mimo-v2.5-pro",
            max_files=100,  # Limits for the demo to run faster
            dry_run=False
        )
        
        # Execute the pipeline
        orchestrator.run()
        
        # Read the generated artifacts to return to the frontend
        context_data = {}
        if orchestrator.context_path.exists():
            context_data = json.loads(orchestrator.context_path.read_text(encoding="utf-8"))
            
        plan_data = {}
        if orchestrator.plan_path.exists():
            plan_data = json.loads(orchestrator.plan_path.read_text(encoding="utf-8"))
            
        val_data = {}
        val_path = orchestrator.artifacts_dir / "validation.json"
        if val_path.exists():
            val_data = json.loads(val_path.read_text(encoding="utf-8"))
            
        # Cleanup the workspace so it doesn't pile up on the VPS disk
        import shutil
        if workspace.exists():
            shutil.rmtree(workspace, ignore_errors=True)
            
        return {
            "status": "success",
            "run_id": run_id,
            "context": context_data,
            "plan": plan_data,
            "validation": val_data
        }
    except Exception as e:
        if workspace.exists():
            shutil.rmtree(workspace, ignore_errors=True)
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
