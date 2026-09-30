# CSV analytics import

`Engine.import_csv` parses the whole file, checks columns, content publication, offset timestamps and finite measurements, then saves snapshots. Required: content_id, observed_at. Supported optional measurements are listed in the main README; blanks remain null. Aliases are normalized. Reimports update matching content/observation/origin records. Use fake data in fixtures and real observations in creator workspaces.
