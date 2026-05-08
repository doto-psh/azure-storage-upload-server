# Azure Blob SAS Upload

This project provides a small FastAPI server that issues short-lived, single-blob
SAS URLs and a Python CLI that uploads files directly to Azure Blob Storage.

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
and write blobs, such as `Storage Blob Data Contributor` scoped to the storage
account.

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

The CLI uses your OS username as the blob path user identifier by default. To
override it:

```bash
uv run azure-upload upload ./file.meta.toml ./file.pdf \
  --server-url http://127.0.0.1:8000 \
  --user-id alice
```

The CLI asks the internal server for a SAS URL, then uploads the file directly
to Azure Blob Storage with `PUT`. The Azure client secret stays only on the
server.
