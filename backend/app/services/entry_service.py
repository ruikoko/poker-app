from app.db import execute_returning, query, execute


def create_entry(
    *,
    source: str,
    entry_type: str,
    site: str | None = None,
    file_name: str | None = None,
    external_id: str | None = None,
    raw_text: str | None = None,
    raw_json: dict | None = None,
    status: str = "new",
    notes: str | None = None,
    import_log_id: int | None = None,
    discord_server: str | None = None,
    discord_channel: str | None = None,
    discord_message_id: str | None = None,
    discord_message_url: str | None = None,
    discord_author: str | None = None,
    discord_posted_at=None,
):
    sql = """
    INSERT INTO entries (
        source, entry_type, site, file_name, external_id,
        raw_text, raw_json, status, notes, import_log_id,
        discord_server, discord_channel, discord_message_id,
        discord_message_url, discord_author, discord_posted_at
    )
    VALUES (
        %(source)s, %(entry_type)s, %(site)s, %(file_name)s, %(external_id)s,
        %(raw_text)s, %(raw_json)s, %(status)s, %(notes)s, %(import_log_id)s,
        %(discord_server)s, %(discord_channel)s, %(discord_message_id)s,
        %(discord_message_url)s, %(discord_author)s, %(discord_posted_at)s
    )
    RETURNING id, source, entry_type, site, file_name, external_id, status, created_at
    """
    return execute_returning(sql, {
        "source": source,
        "entry_type": entry_type,
        "site": site,
        "file_name": file_name,
        "external_id": external_id,
        "raw_text": raw_text,
        "raw_json": raw_json,
        "status": status,
        "notes": notes,
        "import_log_id": import_log_id,
        "discord_server": discord_server,
        "discord_channel": discord_channel,
        "discord_message_id": discord_message_id,
        "discord_message_url": discord_message_url,
        "discord_author": discord_author,
        "discord_posted_at": discord_posted_at,
    })


def list_entries(
    *,
    source: str | None = None,
    entry_type: str | None = None,
    status: str | None = None,
    site: str | None = None,
    page: int = 1,
    page_size: int = 50,
):
    page = max(1, page)
    page_size = min(max(1, page_size), 200)
    offset = (page - 1) * page_size

    where = []
    params = {}

    if source:
        where.append("source = %(source)s")
        params["source"] = source

    if entry_type:
        where.append("entry_type = %(entry_type)s")
        params["entry_type"] = entry_type

    if status:
        where.append("status = %(status)s")
        params["status"] = status

    if site:
        where.append("site = %(site)s")
        params["site"] = site

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    count_sql = f"SELECT COUNT(*) AS total FROM entries {where_sql}"
    total = query(count_sql, params)[0]["total"]

    data_sql = f"""
    SELECT
        id, source, entry_type, site, file_name, external_id,
        status, notes, created_at,
        discord_server, discord_channel, discord_message_id,
        raw_json
    FROM entries
    {where_sql}
    ORDER BY created_at DESC
    LIMIT %(limit)s OFFSET %(offset)s
    """
    params["limit"] = page_size
    params["offset"] = offset
    data = query(data_sql, params)

    pages = (total + page_size - 1) // page_size if total else 0

    return {
        "total": total,
        "page": page,
        "pages": pages,
        "page_size": page_size,
        "data": data,
    }


def get_entry(entry_id: int):
    rows = query(
        """
        SELECT *
        FROM entries
        WHERE id = %s
        """,
        (entry_id,),
    )
    return rows[0] if rows else None


def update_entry(entry_id: int, *, status: str | None = None, notes: str | None = None):
    updates = []
    params = {}

    if status is not None:
        updates.append("status = %(status)s")
        params["status"] = status

    if notes is not None:
        updates.append("notes = %(notes)s")
        params["notes"] = notes

    if not updates:
        return get_entry(entry_id)

    params["id"] = entry_id

    sql = f"""
    UPDATE entries
    SET {', '.join(updates)}
    WHERE id = %(id)s
    """
    execute(sql, params)
    return get_entry(entry_id)
