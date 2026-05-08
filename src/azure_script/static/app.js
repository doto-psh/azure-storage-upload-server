const form = document.querySelector("#upload-form");
const userIdInput = document.querySelector("#user-id");
const metadataInput = document.querySelector("#metadata-file");
const dataInput = document.querySelector("#data-file");
const metadataName = document.querySelector("#metadata-name");
const dataName = document.querySelector("#data-name");
const pairStatus = document.querySelector("#pair-status");
const uploadButton = document.querySelector("#upload-button");
const resetButton = document.querySelector("#reset-button");
const serverStatus = document.querySelector("#server-status");
const actionBadge = document.querySelector("#action-badge");
const message = document.querySelector("#message");
const blobOutput = document.querySelector("#blob-output");
const metadataProgress = document.querySelector("#metadata-progress");
const dataProgress = document.querySelector("#data-progress");
const metadataState = document.querySelector("#metadata-state");
const dataState = document.querySelector("#data-state");

const USER_ID_KEY = "azureUpload.userId";

function metadataBaseName(filename) {
  return filename.endsWith(".meta.toml")
    ? filename.slice(0, -".meta.toml".length)
    : null;
}

function dataBaseName(filename) {
  const dotIndex = filename.lastIndexOf(".");
  return dotIndex > 0 ? filename.slice(0, dotIndex) : null;
}

function validatePair(metadataFile, dataFile) {
  if (!metadataFile || !dataFile) {
    throw new Error("메타데이터 파일과 원본 문서를 모두 선택하세요.");
  }

  const metadataBase = metadataBaseName(metadataFile.name);
  if (!metadataBase) {
    throw new Error("메타데이터 파일명은 <name>.meta.toml 형식이어야 합니다.");
  }

  if (dataFile.name.endsWith(".meta.toml")) {
    throw new Error("원본 문서는 .meta.toml 파일이 아니어야 합니다.");
  }

  const sourceBase = dataBaseName(dataFile.name);
  if (!sourceBase) {
    throw new Error("원본 문서에는 .pdf, .docx 같은 확장자가 있어야 합니다.");
  }

  if (metadataBase !== sourceBase) {
    throw new Error(
      `두 파일의 <name>이 같아야 합니다. 예상 메타 파일명: ${sourceBase}.meta.toml, 선택한 메타 파일명: ${metadataFile.name}`,
    );
  }
}

function guessContentType(file, fallback) {
  if (file.type) {
    return file.type;
  }
  if (file.name.endsWith(".meta.toml")) {
    return "application/toml";
  }
  return fallback;
}

async function sha256Hex(file) {
  const buffer = await file.arrayBuffer();
  const digest = await crypto.subtle.digest("SHA-256", buffer);
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

function setStatus(text) {
  serverStatus.textContent = text;
}

function setBadge(text, type = "") {
  actionBadge.textContent = text;
  actionBadge.className = `badge ${type}`.trim();
}

function setMessage(text, isError = false) {
  message.textContent = text;
  message.classList.toggle("error", isError);
}

function setProgress(kind, value, state) {
  const progress = kind === "metadata" ? metadataProgress : dataProgress;
  const label = kind === "metadata" ? metadataState : dataState;
  progress.value = value;
  label.textContent = state;
}

function resetProgress() {
  setProgress("metadata", 0, "대기");
  setProgress("data", 0, "대기");
}

function setBusy(isBusy) {
  uploadButton.disabled = isBusy;
  resetButton.disabled = isBusy;
  metadataInput.disabled = isBusy;
  dataInput.disabled = isBusy;
  userIdInput.disabled = isBusy;
}

function updateFileLabels() {
  metadataName.textContent = metadataInput.files[0]?.name || "파일을 선택하세요";
  dataName.textContent = dataInput.files[0]?.name || "파일을 선택하세요";
  updatePairStatus();
}

function setPairStatus(text, type = "") {
  pairStatus.textContent = text;
  pairStatus.className = `pair-status ${type}`.trim();
}

function updatePairStatus() {
  const metadataFile = metadataInput.files[0];
  const dataFile = dataInput.files[0];

  if (!metadataFile && !dataFile) {
    setPairStatus("두 파일을 선택하면 규칙 검사 결과가 표시됩니다.");
    return;
  }

  if (!metadataFile || !dataFile) {
    setPairStatus("메타데이터 파일과 원본 문서를 모두 선택해야 합니다.", "warn");
    return;
  }

  const metadataBase = metadataBaseName(metadataFile.name);
  const sourceBase = dataBaseName(dataFile.name);

  if (!metadataBase) {
    setPairStatus("메타데이터 파일명은 반드시 <name>.meta.toml 형식이어야 합니다.", "error");
    return;
  }

  if (!sourceBase || dataFile.name.endsWith(".meta.toml")) {
    setPairStatus("원본 문서는 <name>.pdf, <name>.docx 같은 문서 파일이어야 합니다.", "error");
    return;
  }

  if (metadataBase !== sourceBase) {
    setPairStatus(
      `파일명이 일치하지 않습니다. 원본 문서 기준 예상 메타 파일명은 ${sourceBase}.meta.toml 입니다.`,
      "error",
    );
    return;
  }

  setPairStatus(
    `규칙에 맞습니다. Blob Storage에서는 ${metadataBase} 파일 묶음으로 처리됩니다.`,
    "ok",
  );
}

async function buildPlanError(response) {
  const text = await response.text();
  let detail = text;

  try {
    const parsed = JSON.parse(text);
    if (typeof parsed.detail === "string") {
      detail = parsed.detail;
    } else if (parsed.detail?.message) {
      detail = parsed.detail.message;
    }
  } catch {
    detail = text;
  }

  if (detail.includes("Azure Storage rejected")) {
    return "Azure Storage가 업로드 계획 요청을 거부했습니다. Service Principal 권한과 Storage Account 설정을 확인하세요.";
  }

  if (response.status === 400) {
    return `입력값을 확인하세요. ${detail}`;
  }

  return `업로드 계획 요청에 실패했습니다. 상태 코드: ${response.status}. ${detail}`;
}

async function requestUploadPlan(userId, metadataFile, dataFile) {
  const payload = {
    user_id: userId,
    metadata_filename: metadataFile.name,
    metadata_sha256: await sha256Hex(metadataFile),
    metadata_content_type: guessContentType(metadataFile, "application/toml"),
    metadata_size_bytes: metadataFile.size,
    data_filename: dataFile.name,
    data_content_type: guessContentType(dataFile, "application/octet-stream"),
    data_size_bytes: dataFile.size,
  };

  const response = await fetch("/uploads/plan", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(await buildPlanError(response));
  }

  return response.json();
}

function uploadWithProgress(uploadTarget, file) {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("PUT", uploadTarget.upload_url);

    Object.entries(uploadTarget.required_headers).forEach(([key, value]) => {
      request.setRequestHeader(key, value);
    });

    request.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        setProgress(
          uploadTarget.kind,
          Math.round((event.loaded / event.total) * 100),
          "업로드 중",
        );
      }
    };

    request.onload = () => {
      if (request.status === 201 || request.status === 202) {
        setProgress(uploadTarget.kind, 100, "완료");
        resolve(uploadTarget.blob_name);
        return;
      }
      reject(
        new Error(
          `Azure Blob Storage 업로드에 실패했습니다. 상태 코드: ${request.status}. ${request.responseText}`,
        ),
      );
    };

    request.onerror = () => {
      reject(
        new Error(
          "브라우저에서 Azure Blob Storage 업로드가 차단되었습니다. Storage Account의 Blob service CORS 설정에 현재 UI 주소를 허용하세요.",
        ),
      );
    };

    request.send(file);
  });
}

async function handleSubmit(event) {
  event.preventDefault();

  const userId = userIdInput.value.trim();
  const metadataFile = metadataInput.files[0];
  const dataFile = dataInput.files[0];

  try {
    if (!userId) {
      throw new Error("사용자 ID를 입력하세요.");
    }
    validatePair(metadataFile, dataFile);
    localStorage.setItem(USER_ID_KEY, userId);

    setBusy(true);
    resetProgress();
    setBadge("확인 중");
    setStatus("처리 중");
    setMessage("기존 메타데이터 파일과 비교하고 있습니다.");
    blobOutput.textContent = "Blob Storage 내 저장 경로를 확인 중입니다.";

    const plan = await requestUploadPlan(userId, metadataFile, dataFile);

    if (plan.action === "skip") {
      setBadge("스킵", "skip");
      setStatus("대기 중");
      setProgress("metadata", 100, "스킵");
      setProgress("data", 100, "스킵");
      setMessage("기존 메타데이터 파일 내용과 동일하여 업로드하지 않았습니다.");
      blobOutput.textContent = [plan.metadata_blob_name, plan.data_blob_name].join("\n");
      return;
    }

    setBadge(plan.action === "update" ? "수정" : "업로드", plan.action);
    setMessage(
      plan.action === "update"
        ? "메타데이터 파일 내용이 변경되어 두 파일을 수정하고 있습니다."
        : "기존 파일이 없어 두 파일을 새로 업로드하고 있습니다.",
    );

    const filesByKind = {
      metadata: metadataFile,
      data: dataFile,
    };
    const uploaded = [];
    for (const uploadTarget of plan.uploads) {
      uploaded.push(await uploadWithProgress(uploadTarget, filesByKind[uploadTarget.kind]));
    }

    setStatus("대기 중");
    setMessage(
      plan.action === "update"
        ? "수정이 완료되었습니다."
        : "업로드가 완료되었습니다.",
    );
    blobOutput.textContent = uploaded.join("\n");
  } catch (error) {
    setStatus("대기 중");
    setBadge("오류", "error");
    setMessage(error instanceof Error ? error.message : String(error), true);
  } finally {
    setBusy(false);
  }
}

function handleReset() {
  form.reset();
  updateFileLabels();
  resetProgress();
  setBadge("대기");
  setStatus("대기 중");
  setMessage("메타데이터 파일과 원본 문서를 선택하세요.");
  blobOutput.textContent = "아직 생성된 경로가 없습니다.";
}

userIdInput.value = localStorage.getItem(USER_ID_KEY) || "";
metadataInput.addEventListener("change", updateFileLabels);
dataInput.addEventListener("change", updateFileLabels);
form.addEventListener("submit", handleSubmit);
resetButton.addEventListener("click", handleReset);
