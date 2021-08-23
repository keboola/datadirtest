import os
from pathlib import Path

if __name__ == "__main__":
    data_dir = Path(os.environ["KBC_DATADIR"])

    out_file = Path(f'{os.environ["KBC_DATADIR"]}/out/tables/table.csv')
    out_file.parent.mkdir(parents=True, exist_ok=True)

    open(out_file, 'a').close()
    print('file created')
