import json
import os
from pathlib import Path

if __name__ == "__main__":
    data_dir = Path(os.environ["KBC_DATADIR"])

    in_state_path = Path(f'{os.environ["KBC_DATADIR"]}/in/state.json')
    last_value = 'state'
    if os.path.exists(in_state_path):
        with open(in_state_path, 'r') as inp:
            last_state = json.load(inp)
            last_value = last_state.get('last_value') + '02' if last_state.get('last_value') else last_value

    out_file = Path(f'{os.environ["KBC_DATADIR"]}/out/tables/table.csv')
    out_file.parent.mkdir(parents=True, exist_ok=True)

    with open(out_file, 'w+') as outp:
        outp.write(last_value)

    out_state = Path(f'{os.environ["KBC_DATADIR"]}/out/state.json')
    with open(out_state, 'w+') as state_out:
        json.dump({"last_value": last_value}, state_out)

    print('file created')
