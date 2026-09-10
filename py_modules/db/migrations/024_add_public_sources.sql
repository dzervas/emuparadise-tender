CREATE TABLE public_sources (
    rom_id INTEGER PRIMARY KEY CHECK (rom_id >= 4503599627370496 AND rom_id <= 9007199254740991),
    catalogue TEXT NOT NULL,
    external_id TEXT NOT NULL,
    detail_json TEXT NOT NULL,
    download_provider TEXT NOT NULL,
    download_page TEXT NOT NULL,
    UNIQUE (catalogue, external_id)
) STRICT;
