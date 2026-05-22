import os

VARIABLES_PATH = None


class Database:
    def __init__(self, path=None):
        self._path = path or VARIABLES_PATH
        self._variables = {}
        self._tables = {"b++2variables"}
        if self._path and os.path.exists(self._path):
            self._load(self._path)

    def _load(self, path):
        with open(path) as f:
            for line in f:
                line = line.rstrip("\n")
                if not line:
                    continue
                parts = line.split("\t")
                if len(parts) < 4:
                    continue
                name = parts[0]
                value = parts[1]
                vtype = int(parts[2])
                owner = parts[3]
                self._variables[name] = (value, vtype, owner)

    def get_tables(self):
        return list(self._tables)

    def get_columns(self, table, include_type=False):
        if table != "b++2variables":
            raise NameError(f"Table {table} not found")
        cols = ["name", "value", "type", "owner"]
        if include_type:
            return [("name", "text"), ("value", "text"), ("type", "integer"), ("owner", "text")]
        return cols

    def get_entries(self, table, limit=None, columns=None, conditions=None):
        if table != "b++2variables":
            raise NameError(f"Table {table} not found")
        columns = columns or ["name", "value", "type", "owner"]
        conditions = conditions or {}

        all_cols = ["name", "value", "type", "owner"]
        col_idx = [all_cols.index(c) for c in columns]

        results = []
        for name, (value, vtype, owner) in self._variables.items():
            row = (name, value, vtype, owner)
            match = True
            for ck, cv in conditions.items():
                ci = all_cols.index(ck)
                if str(row[ci]) != str(cv):
                    match = False
                    break
            if match:
                results.append(tuple(row[i] for i in col_idx))
            if limit and len(results) >= limit:
                break
        return results

    def add_entry(self, table, entry):
        if table != "b++2variables":
            raise NameError(f"Table {table} not found")
        name, value, vtype, owner = entry
        self._variables[name] = (str(value), int(vtype), str(owner))

    def edit_entry(self, table, entry=None, conditions=None):
        if table != "b++2variables":
            raise NameError(f"Table {table} not found")
        entry = entry or {}
        conditions = conditions or {}
        for name in list(self._variables.keys()):
            value, vtype, owner = self._variables[name]
            match = True
            for ck, cv in conditions.items():
                if ck == "name" and name != str(cv):
                    match = False
                    break
            if match:
                new_val = entry.get("value", value)
                new_type = entry.get("type", vtype)
                self._variables[name] = (str(new_val), int(new_type), owner)
