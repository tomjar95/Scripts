import os
import csv
import re
from datetime import date, timedelta
from collections import Counter, defaultdict


def read_files():
    """
    Finds yesterday's and today's Rubrik 
    Protection Report CSV files in the current directory.
    """
    prefix = "Protection-Report---Quarterly-review_"
    today = date.today()
    weekday = today.weekday()

    yesterday_str = (
        (today - timedelta(days=3)).isoformat()
        if weekday == 0 else 
        (today - timedelta(days=1)).isoformat()
    )

    today_str = today.isoformat()
    folder = "."

    def find_file(date_str):
        return [
            f for f in os.listdir(folder)
            if os.path.isfile(os.path.join(folder, f))
            and prefix + date_str in f
        ]
    
    today_files = find_file(today_str)
    yesterday_files = find_file(yesterday_str)

    if not today_files:
        raise FileNotFoundError(f"No file found for today: {today_str}")
    if not yesterday_files:
        raise FileNotFoundError(f"No file found for yesterday: {yesterday_str}")
    
    return (
        os.path.join(folder, today_files[0]),
        os.path.join(folder, yesterday_files[0]),
        today_str,
        yesterday_str,
    )

EXPECTED_COLUMNS = [
    "Object",
    "Object Type",
    "Object State",
    "Protection Status",
    "SLA Domain",
    "Cluster",
    "Location",
]

EXCLUDE_COLUMNS = [
    "Last Successful Backup",
    "Latest Archival Snapshot",
    "Latest Replication Snapshot",
]

EXCLUDED_OBJECT_TYPES = [
    "SQL Server DB",
    "Oracle DB",
]


def normalize_header(h: str) -> str:
    """
    Normalizes a header string by removing non-alphanumeric characters.
    """
    return (h or "").replace("\ufeff", "").strip()


def normalize_value(v: str) -> str:
    """
    Normalizes a value string by removing non-alphanumeric characters.
    """
    v = "" if v is None else str(v)
    return " ".join(v.strip().split())


def is_excluded_object_type(row:dict) -> bool:
    """
    Checks if the object type in the row is in the excluded list.
    """
    return row.get("Object Type") in EXCLUDED_OBJECT_TYPES


def is_active(row: dict) -> bool:
    """
    Checks if the object state in the row is 'Active'.
    """
    return (row.get("Object State") or "").strip().lower() == "active"


def is_relic(row: dict) -> bool:
    """
    Checks if the object state in the row is 'Relic'.
    """
    return (row.get("Object State") or "").strip().lower() == "relic"


def protection_status(row: dict) -> str:
    """
    Returns the protection status of the object in the row.
    """
    return (row.get("Protection Status") or "").strip().lower()


def is_protected(row: dict) -> bool:
    """
    Checks if the protection status in the row is 'Protected'.
    """
    return protection_status(row) == "protected"


def is_unprotected(row: dict) -> bool:
    """
    Checks if the protection status in the row is 'Unprotected'.
    """
    return protection_status(row) in ("donotprotect", "nosla")


def has_sla_domain(row: dict) -> bool:
    """
    Checks if the SLA Domain in the row is not empty or unprotected.
    """
    sla = (row.get("SLA Domain") or "").strip().lower()
    return sla not in ("", "nosla", "dont protect", "unprotected", "don't protect")


def is_random_object_name(name: str) -> bool:
    """
    Checks if the object name matches a pattern of random characters.
    """
    if not name or len(name.strip()) < 30:
        return False
    s = name.strip()
    return (
        re.fullmatch(r"[A-Za-z0-9]+", s) is not None
        and any(c.isalpha() for c in s)
        and any(c.isdigit() for c in s)
    )


def read_csv_rows(path:str):
    """
    Reads a CSV file and returns a list of dictionaries representing the rows.
    """
    rows = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        reader.fieldnames = [normalize_header(h) for h in reader.fieldnames]
        missing_columns = [c for c in EXPECTED_COLUMNS if c not in reader.fieldnames]
        if missing_columns:
            raise ValueError(f"Missing expected columns in {path}: {missing_columns}")
        
        used_columns = [c for c in reader.fieldnames if c not in EXCLUDE_COLUMNS]
        for row in reader:
            rows.append({k: normalize_value(row.get(k)) for k in used_columns})
    return rows


def row_signature(row: dict) -> str:
    """
    Generates a unique signature for a row based on the expected columns.
    """
    return tuple(row.get(c, "") for c in EXPECTED_COLUMNS)


def sig_to_row(sig):
    """
    Converts a signature tuple back to a row dictionary.
    """
    return dict(zip(EXPECTED_COLUMNS, sig))


def entity_id(row: dict):
    """
    Generates a unique identifier for an entity based on its Object, Location, and Object Type.
    """
    return (
        row.get("Object", ""),
        row.get("Location", ""),
        row.get("Object Type", ""),
    )


def index_by_entity(rows):
    """
    Indexes rows by their entity identifier.
    """
    idx = defaultdict(list)
    for r in rows:
        idx[entity_id(r)].append(r)
    return idx


def newly_added_and_expired(old_rows, new_rows):
    """
    Identifies newly protected, newly unprotected, and expired objects
    by comparing old and new rows.
    """
    old_c = Counter(row_signature(r) for r in old_rows)
    new_c = Counter(row_signature(r) for r in new_rows)

    old_by_entity = index_by_entity(old_rows)
    new_by_entity = index_by_entity(new_rows)

    old_entities = set(old_by_entity.keys())

    newly_protected = []
    newly_unprotected = []
    expired = []

    for r in new_rows:
        sig = row_signature(r)

        if new_c[sig] <= old_c[sig]:
            continue

        eid = entity_id(r)
        if eid in old_entities:
            old_versions = old_by_entity[eid]

            only_state_change = any(
                is_active(o) and is_relic(r) and
                all(
                    normalize_value(o.get(c)) == normalize_value(r.get(c))
                    for c in EXPECTED_COLUMNS
                    if c != "Object State"
                )
                for o in old_versions
            )

            if only_state_change:
                continue

        if is_protected(r):
            newly_protected.append(r)
        elif is_unprotected(r):
            newly_unprotected.append(r)

    for r in old_rows:
        sig = row_signature(r)

        if old_c[sig] <= new_c[sig]:
            continue

        eid = entity_id(r)
        if eid in new_by_entity:
            new_versions = new_by_entity[eid]

            only_state_change = any(
                is_active(r) and is_relic(n) and
                all(
                    normalize_value(r.get(c)) == normalize_value(n.get(c))
                    for c in EXPECTED_COLUMNS
                    if c != "Object State"
                )
                for n in new_versions
            )

            if only_state_change:
                expired.append(r)
                continue

        expired.append(r)

    return newly_protected, newly_unprotected, expired


def transitions(old_rows, new_rows, require_no_active_for_relic=True):
    """
    Identifies transitions between protected, unprotected, and relic states
    by comparing old and new rows.
    """
    old_idx = index_by_entity(old_rows)
    new_idx = index_by_entity(new_rows)

    p_to_u, p_to_r, u_to_p = [], [], []

    for ent in old_idx.keys() & new_idx.keys():
        old_list = old_idx[ent]
        new_list = new_idx[ent]

        old_p = any(is_active(r) and is_protected(r) for r in old_list)
        old_u = any(is_active(r) and is_unprotected(r) for r in old_list)
        new_p = any(is_active(r) and is_protected(r) for r in new_list)
        new_u = any(is_active(r) and is_unprotected(r) for r in new_list)

        new_p_rows = [r for r in new_list if is_active(r) and is_protected(r)]
        new_u_rows = [r for r in new_list if is_active(r) and is_unprotected(r)]
        new_r_rows = [r for r in new_list if is_relic(r)]
        new_has_active = any(is_active(r) for r in new_list)

        if old_u and not old_p and new_p and not new_u:
            u_to_p.extend(new_p_rows)
            continue

        if old_p and not old_u and new_u and not new_p:
            p_to_u.extend(new_u_rows)
            continue

        if old_p and new_r_rows:
            if not require_no_active_for_relic or not new_has_active:
                p_to_r.extend(new_r_rows)

    return p_to_u, p_to_r, u_to_p


def print_table_cli(title, rows, columns, filter_random=True):
    """
    Prints a formatted table of rows to the command line, filtering out excluded object types
    and optionally filtering out rows with random object names.
    """
    filtered = []

    for r in rows:
        obj = (r.get("Object") or "").strip()
        if not obj or obj.lower() == "none":
            continue

        if is_excluded_object_type(r):
            continue

        if filter_random and is_random_object_name(obj):
            continue

        filtered.append(r)

    if not filtered:
        return
    
    print(f"\n{title}")

    filtered.sort(key=lambda r: (
        (r.get("Object") or "").lower(),
        (r.get("Location") or "").lower(),
        (r.get("Object Type") or "").lower(), 
    ))
    
    widths = {
        c: max(len(c), max(len(r.get(c, "")) for r in filtered)) + 2
               for c in columns
    }

    for r in filtered:
        print("".join(str(r.get(c, "")). ljust(widths[c]) for c in columns))


def main():
    """
    Main function to compare yesterday's and today's Rubrik Protection Report CSV files
    and print the differences in a formatted table.
    """
    t_path, y_path, _, _ = read_files()
    old_rows = read_csv_rows(y_path)
    new_rows = read_csv_rows(t_path)

    newly_p, newly_u, expired = newly_added_and_expired(old_rows, new_rows)
    p_to_u, p_to_r, u_to_p = transitions(old_rows, new_rows)

    transition_entities = {entity_id(r) for r in (p_to_u + p_to_r + u_to_p)}
    transition_sigs = {row_signature(r) for r in (p_to_u + p_to_r + u_to_p)}

    newly_p = [r for r in newly_p if row_signature(r) not in transition_sigs]
    newly_u = [r for r in newly_u if row_signature(r) not in transition_sigs]
    expired = [r for r in expired if entity_id(r) not in transition_entities]

    if (newly_p or newly_u or expired or p_to_u or p_to_r or u_to_p):
        print("Protection report", date.today().strftime("%d-%m-%Y"))
    if newly_p:
        print_table_cli("Newly Protected Objects", newly_p, EXPECTED_COLUMNS)
    if newly_u:
        print_table_cli("Newly Unprotected Objects", newly_u, EXPECTED_COLUMNS)
    if expired:
        print_table_cli("Expired Objects", expired, EXPECTED_COLUMNS)
    if p_to_u:
        print_table_cli("Transition: Protected to Unprotected", p_to_u, EXPECTED_COLUMNS)
    if p_to_r:
        print_table_cli("Transition: Protected to Relic", p_to_r, EXPECTED_COLUMNS)
    if u_to_p:
        print_table_cli("Transition: Unprotected to Protected", u_to_p, EXPECTED_COLUMNS)


if __name__ == "__main__":
    main()