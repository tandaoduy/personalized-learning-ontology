"""Guard resource paths after moving the Flask package under backend/app."""
from pathlib import Path

from backend.app.config import Config
from backend.app.routes.auth_routes import ACCOUNTS_PATH
from backend.app.routes.recommendation_routes import STUDENT_FEEDBACK_PATH
from backend.app.routes.advisor_role_routes import DATA_DIR


def test_runtime_data_stays_in_project_data():
    root = Path(__file__).resolve().parents[2]
    assert Path(Config.BASE_DIR) == root
    assert Path(Config.STUDENT_DATA_JSON).parent == root / "data"
    assert Path(Config.STUDENT_DATA_CSV).parent == root / "data"
    assert ACCOUNTS_PATH == root / "data" / "accounts.json"
    assert STUDENT_FEEDBACK_PATH == root / "data" / "student_feedback.json"
    assert DATA_DIR == root / "data"


def test_ontology_and_flask_resources_exist():
    root = Path(__file__).resolve().parents[2]
    assert Path(Config.ONTOLOGY_PATH) == root / "knowledge" / "ontology" / "ontology_v23.rdf"
    assert Path(Config.ONTOLOGY_PATH).is_file()
    from backend.app.app import app
    assert Path(app.root_path) == root / "backend" / "app"
    assert (Path(app.root_path) / app.template_folder / "base.html").is_file()
    assert Path(app.static_folder).is_dir()
