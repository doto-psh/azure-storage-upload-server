# Azure Blob SAS Upload

This project provides a small FastAPI server that decides whether a paired
metadata/document upload should be skipped, uploaded, or updated, then issues
short-lived SAS URLs for the files that need to be written.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full architecture, Azure role
requirements, and user upload instructions.

## Setup

Install dependencies:

```bash
uv sync
```

Create local config:

```bash
cp .env.example .env
```

Update `.env` with your Azure Storage account, container, and service principal
values. The service principal needs permission to generate user delegation keys
and read/write blobs, such as `Storage Blob Data Contributor` scoped to the
storage account.

## Run the Server

```bash
uv run uvicorn azure_script.server:app --reload
```

## Upload Files

```bash
uv run azure-upload upload ./file.meta.toml ./file.pdf \
  --server-url http://127.0.0.1:8000
```

The upload command requires exactly two files:

- `<name>.meta.toml`
- `<name>.<extension>`, such as `<name>.pdf` or `<name>.docx`

Both files must share the same `<name>`. For example, `report.meta.toml` and
`report.pdf` are valid. `report.meta.toml` and `invoice.pdf` are rejected before
any Azure upload starts.

The server compares the local `.meta.toml` content with the existing metadata
blob for the same `user_id` and `<name>`:

- Same metadata content: skip both files.
- Same metadata filename but different metadata content: update both files.
- No existing metadata filename: upload both files.

The CLI uses your OS username as the blob path user identifier by default. To
override it:

```bash
uv run azure-upload upload ./file.meta.toml ./file.pdf \
  --server-url http://127.0.0.1:8000 \
  --user-id alice
```

The CLI asks the internal server for an upload plan. When the plan is `upload`
or `update`, it uploads both files directly to Azure Blob Storage with `PUT`.
The Azure client secret stays only on the server.
