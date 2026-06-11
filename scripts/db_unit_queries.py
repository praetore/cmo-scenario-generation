"""Query unit loadouts and weapon fit from CMO SQLite databases."""

from cmo_db import open_db


def get_loadouts(aircraft_id, series=None, version=None, db_path=None):
    db = open_db(db_path=db_path, series=series, version=version)
    cursor = db.cursor

    dal_query = "SELECT ComponentID FROM DataAircraftLoadouts WHERE ID = ?"
    params = [aircraft_id]
    dal_query, params = db.append_meta_filters(dal_query, params)
    cursor.execute(dal_query, params)
    dal_rows = cursor.fetchall()

    if not dal_rows:
        db.close()
        return []

    comp_ids = [row[0] for row in dal_rows]
    series = series or db.series
    version = version or db.version

    placeholders = ",".join(["?"] * len(comp_ids))
    dl_query = f"SELECT ID, Name, {db.meta_select()} FROM DataLoadout WHERE ID IN ({placeholders})"
    dl_params = list(comp_ids)
    dl_query, dl_params = db.append_meta_filters(dl_query, dl_params)
    dl_query += " ORDER BY ID ASC"

    cursor.execute(dl_query, dl_params)
    results = cursor.fetchall()
    db.close()
    return results


def get_unit_weapons(unit_id, unit_type, series=None, version=None, db_path=None):
    db = open_db(db_path=db_path, series=series, version=version)
    cursor = db.cursor

    table_map = {
        "DataShip": ("DataShipMagazines", "DataShipMounts"),
        "DataFacility": ("DataFacilityMagazines", "DataFacilityMounts"),
        "DataSubmarine": ("DataSubmarineMagazines", "DataSubmarineMounts"),
        "DataGroundUnit": ("DataGroundUnitMagazines", "DataGroundUnitMounts"),
        "DataAircraft": (None, "DataAircraftMounts"),
    }

    if unit_type not in table_map:
        db.close()
        return None

    mag_table, mount_table = table_map[unit_type]
    results = {"magazines": [], "mounts": []}

    try:
        unit_params = [int(unit_id)]
    except ValueError:
        unit_params = [unit_id]

    if mag_table:
        query = f"SELECT ComponentID FROM {mag_table} WHERE ID = ?"
        params = list(unit_params)
        query, params = db.append_meta_filters(query, params)
        cursor.execute(query, params)
        mag_links = cursor.fetchall()

        for row in mag_links:
            mag_id = row[0]
            ser, ver = db.series, db.version

            name_query = "SELECT Name FROM DataMagazine WHERE ID = ?"
            name_params = [mag_id]
            name_query, name_params = db.append_meta_filters(name_query, name_params)
            cursor.execute(name_query, name_params)
            mag_res = cursor.fetchone()
            mag_name = mag_res[0] if mag_res else "Unknown Magazine"

            weapons_query = """
                SELECT mw.ComponentID, w.Name, 0 as Quantity
                FROM DataMagazineWeapons mw
                LEFT JOIN DataWeapon w ON mw.ComponentID = w.ID
            """
            weapons_query = db.append_join_meta(weapons_query, "mw", "w")
            weapons_query += " WHERE mw.ID = ?"
            weapon_params = [mag_id]
            weapons_query, weapon_params = db.append_meta_filters(weapons_query, weapon_params, "mw")
            cursor.execute(weapons_query, weapon_params)
            weapons = cursor.fetchall()
            results["magazines"].append(
                {"id": mag_id, "name": mag_name, "weapons": weapons, "series": ser, "version": ver}
            )

    if mount_table:
        query = f"SELECT ComponentID FROM {mount_table} WHERE ID = ?"
        params = list(unit_params)
        query, params = db.append_meta_filters(query, params)
        cursor.execute(query, params)
        mount_links = cursor.fetchall()

        for row in mount_links:
            mount_id = row[0]
            ser, ver = db.series, db.version

            name_query = "SELECT Name FROM DataMount WHERE ID = ?"
            name_params = [mount_id]
            name_query, name_params = db.append_meta_filters(name_query, name_params)
            cursor.execute(name_query, name_params)
            mount_res = cursor.fetchone()
            mount_name = mount_res[0] if mount_res else "Unknown Mount"

            weapons_query = """
                SELECT mw.ComponentID, w.Name, 0 as Load
                FROM DataMountWeapons mw
                LEFT JOIN DataWeapon w ON mw.ComponentID = w.ID
            """
            weapons_query = db.append_join_meta(weapons_query, "mw", "w")
            weapons_query += " WHERE mw.ID = ?"
            weapon_params = [mount_id]
            weapons_query, weapon_params = db.append_meta_filters(weapons_query, weapon_params, "mw")
            cursor.execute(weapons_query, weapon_params)
            weapons = cursor.fetchall()
            results["mounts"].append(
                {"id": mount_id, "name": mount_name, "weapons": weapons, "series": ser, "version": ver}
            )

    db.close()
    return results
