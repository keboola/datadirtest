import json
import os
from pathlib import Path
import logging

if __name__ == "__main__":
    data_dir = Path(os.environ["KBC_DATADIR"])
    Path.mkdir(data_dir / 'out' / 'tables', parents=True, exist_ok=True)


    print('file created')

    try:
        with os.scandir(Path.joinpath(data_dir, 'artifacts/in/runs/')) as runs:
            for run in runs:
                for file in os.listdir(run):
                    print(f"Found artefact in the previous run: {file}")
    except FileNotFoundError:
        logging.error("No previous run artefacts found")

    try:
        for file in os.listdir(Path.joinpath(data_dir, 'artifacts/in/shared/')):
            print(f"Found artefact in the shared artifacts: {file}")

    except FileNotFoundError:
        logging.error("No shared artefacts found")

    try:
        with os.scandir(Path.joinpath(data_dir, 'artifacts/in/custom/')) as runs:
            for run in runs:
                for file in os.listdir(run):
                    print(f"Found custom artifact: {file}")

    except FileNotFoundError:
        logging.error("No custom artefacts found")

    current_artifact_out_path = Path.joinpath(data_dir, 'artifacts/out/current/artefact.txt')
    current_artifact_out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(current_artifact_out_path, 'w') as f:
        f.write('test')

    shared_artifact_out_path = Path.joinpath(data_dir, 'artifacts/out/shared/artefact-shared.txt')
    shared_artifact_out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(shared_artifact_out_path, 'w') as f:
        f.write('test')
    pass