(function () {
  const body = document.body;
  const modal = document.getElementById("videoModal");
  const openCreateModalButton = document.getElementById("openCreateModal");
  const closeModalButtons = Array.from(document.querySelectorAll("[data-close-modal]"));
  const deviceSelect = document.getElementById("deviceSelect");
  const platformSelect = document.getElementById("platformSelect");
  const accountSelect = document.getElementById("accountSelect");
  const platformHint = document.getElementById("platformHint");
  const accountHint = document.getElementById("accountHint");
  const searchInput = document.getElementById("videoSearchInput");
  const statusFilter = document.getElementById("statusFilter");
  const resultsMeta = document.getElementById("resultsMeta");
  const emptyFilterState = document.getElementById("emptyFilterState");
  const videoCards = Array.from(document.querySelectorAll(".video-card"));
  const totalItems = Number(resultsMeta?.dataset.totalItems || videoCards.length);
  const inlineReferenceForms = Array.from(document.querySelectorAll(".inline-reference-form"));
  const uploadPanels = Array.from(document.querySelectorAll(".js-upload-panel"));
  const uploadSummaryValues = Array.from(document.querySelectorAll(".js-upload-summary-value"));
  const videoForms = Array.from(document.querySelectorAll(".video-form"));
  const actionForms = Array.from(document.querySelectorAll("form"));

  function isEditingMode() {
    return body?.dataset.editing === "true";
  }

  function openModal() {
    if (!modal) {
      return;
    }
    modal.classList.add("is-open");
    modal.setAttribute("aria-hidden", "false");
    body.classList.add("modal-active");
  }

  function closeModal() {
    if (!modal) {
      return;
    }

    if (isEditingMode()) {
      const nextUrl = new URL(window.location.href);
      nextUrl.searchParams.delete("edit");
      nextUrl.searchParams.delete("edit_upload");
      window.location.href = `${nextUrl.pathname}${nextUrl.search}`;
      return;
    }

    modal.classList.remove("is-open");
    modal.setAttribute("aria-hidden", "true");
    body.classList.remove("modal-active");
  }

  function setHint(element, message, isError) {
    if (!element) {
      return;
    }
    element.textContent = message;
    element.classList.toggle("field-note-error", Boolean(isError));
  }

  function setInlineStatus(element, message, type) {
    if (!element) {
      return;
    }
    element.textContent = message;
    element.classList.remove("is-success", "is-error");
    if (type) {
      element.classList.add(type);
    }
  }

  function populateSelect(select, items, selectedValue, emptyMessage) {
    if (!select) {
      return;
    }

    select.innerHTML = "";

    if (!items.length) {
      const option = document.createElement("option");
      option.value = "";
      option.textContent = emptyMessage;
      select.appendChild(option);
      return;
    }

    items.forEach((item) => {
      const option = document.createElement("option");
      option.value = String(item.id);
      option.textContent = item.label;
      if (selectedValue && String(item.id) === String(selectedValue)) {
        option.selected = true;
      }
      select.appendChild(option);
    });
  }

  async function fetchReference(url) {
    const response = await fetch(url, {
      headers: {
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const payload = await response.json();
    if (!payload.success) {
      throw new Error(payload.message || "Request failed");
    }
    return payload.items || [];
  }

  async function loadAccounts(selectedAccountId) {
    if (!platformSelect || !accountSelect) {
      return;
    }

    const platformId = platformSelect.value;

    if (!platformId) {
      populateSelect(accountSelect, [], "", "เลือก Platform ก่อน");
      accountSelect.disabled = true;
      setHint(accountHint, "ยังไม่มี Platform ที่เลือก", false);
      return;
    }

    accountSelect.disabled = true;
    setHint(accountHint, "กำลังโหลด Account...", false);

    try {
      const items = await fetchReference(`/reference/device-platforms/${platformId}/accounts`);
      populateSelect(accountSelect, items, selectedAccountId, "ไม่พบ Account");
      accountSelect.disabled = !items.length;
      setHint(accountHint, `${items.length} รายการสำหรับ Platform นี้`, false);
    } catch (error) {
      populateSelect(accountSelect, [], "", "โหลด Account ไม่สำเร็จ");
      accountSelect.disabled = true;
      setHint(accountHint, `โหลด Account ไม่สำเร็จ: ${error.message}`, true);
    }
  }

  async function loadPlatforms(selectedPlatformId, selectedAccountId) {
    if (!deviceSelect || !platformSelect || !accountSelect) {
      return;
    }

    const deviceId = deviceSelect.value;

    if (!deviceId) {
      populateSelect(platformSelect, [], "", "เลือก Device ก่อน");
      platformSelect.disabled = true;
      populateSelect(accountSelect, [], "", "เลือก Platform ก่อน");
      accountSelect.disabled = true;
      setHint(platformHint, "ยังไม่มี Device ที่เลือก", false);
      setHint(accountHint, "ยังไม่มี Platform ที่เลือก", false);
      return;
    }

    platformSelect.disabled = true;
    accountSelect.disabled = true;
    setHint(platformHint, "กำลังโหลด Platform...", false);

    try {
      const items = await fetchReference(`/reference/devices/${deviceId}/platforms`);
      populateSelect(platformSelect, items, selectedPlatformId, "ไม่พบ Platform");
      platformSelect.disabled = !items.length;
      setHint(platformHint, `${items.length} รายการสำหรับ Device นี้`, false);
      await loadAccounts(selectedAccountId);
    } catch (error) {
      populateSelect(platformSelect, [], "", "โหลด Platform ไม่สำเร็จ");
      platformSelect.disabled = true;
      populateSelect(accountSelect, [], "", "โหลด Account ไม่สำเร็จ");
      accountSelect.disabled = true;
      setHint(platformHint, `โหลด Platform ไม่สำเร็จ: ${error.message}`, true);
      setHint(accountHint, "ยังโหลด Account ไม่ได้", true);
    }
  }

  function updateFilterUI(visibleCount) {
    if (resultsMeta) {
      if (totalItems > videoCards.length) {
        resultsMeta.textContent = `แสดง ${visibleCount} จาก ${videoCards.length} รายการในหน้านี้ (ทั้งหมด ${totalItems})`;
      } else {
        resultsMeta.textContent = `แสดง ${visibleCount} จาก ${totalItems} รายการ`;
      }
    }

    if (emptyFilterState) {
      emptyFilterState.classList.toggle("is-hidden", visibleCount > 0);
    }
  }

  function applyFilters() {
    if (!videoCards.length) {
      return;
    }

    const query = (searchInput?.value || "").trim().toLowerCase();
    const selectedStatus = statusFilter?.value || "all";
    let visibleCount = 0;

    videoCards.forEach((card) => {
      const haystack = card.dataset.search || "";
      const status = card.dataset.status || "";
      const matchQuery = !query || haystack.includes(query);
      const matchStatus = selectedStatus === "all" || status === selectedStatus;
      const shouldShow = matchQuery && matchStatus;

      card.classList.toggle("is-hidden", !shouldShow);
      if (shouldShow) {
        visibleCount += 1;
      }
    });

    updateFilterUI(visibleCount);
  }

  function refreshCardSearch(card, form) {
    if (!card || !form) {
      return;
    }

    const baseSearch = card.dataset.baseSearch || "";
    const deviceText = form.querySelector(".inline-device")?.selectedOptions?.[0]?.textContent || "";
    const platformText = form.querySelector(".inline-platform")?.selectedOptions?.[0]?.textContent || "";
    const accountText = form.querySelector(".inline-account")?.selectedOptions?.[0]?.textContent || "";
    const workflowText = form.querySelector(".inline-workflow")?.selectedOptions?.[0]?.textContent || "";

    card.dataset.search = `${baseSearch} ${deviceText} ${platformText} ${accountText} ${workflowText}`.toLowerCase();
  }

  function normalizeUploadStateClass(status) {
    return `upload-state-${String(status || "not_sent").toLowerCase().replaceAll("_", "-")}`;
  }

  function updateUploadSummary(item) {
    if (!item || !uploadSummaryValues.length) {
      return;
    }

    uploadSummaryValues.forEach((element) => {
      const key = element.dataset.summaryKey;
      if (!key) {
        return;
      }
      element.textContent = String(item[key] ?? 0);
    });
  }

  function fieldValue(form, name) {
    return String(form.elements[name]?.value || "").trim();
  }

  function clearValidationErrors(form) {
    form.querySelectorAll(".field-error").forEach((element) => element.remove());
    form.querySelectorAll(".has-error").forEach((element) => element.classList.remove("has-error"));
  }

  function showFieldError(form, name, message) {
    const field = form.elements[name];
    const wrapper = field?.closest(".field");
    if (!field || !wrapper) {
      return;
    }

    wrapper.classList.add("has-error");
    const error = document.createElement("small");
    error.className = "field-error";
    error.textContent = message;
    wrapper.appendChild(error);
  }

  function validateVideoForm(form) {
    clearValidationErrors(form);
    const errors = [];

    [
      ["device_id", "กรุณาเลือก Device"],
      ["workflow_id", "กรุณาเลือก Workflow"],
      ["title", "กรุณากรอก Title"],
      ["status", "กรุณาเลือก Status"],
    ].forEach(([name, message]) => {
      if (!fieldValue(form, name)) {
        errors.push([name, message]);
      }
    });

    if (!fieldValue(form, "video_url") && !fieldValue(form, "local_video_path")) {
      errors.push(["video_url", "กรุณากรอก Video URL หรือ Local Video Path อย่างน้อยหนึ่งช่อง"]);
      errors.push(["local_video_path", "กรุณากรอก Video URL หรือ Local Video Path อย่างน้อยหนึ่งช่อง"]);
    }

    const metadata = fieldValue(form, "metadata_json");
    if (metadata) {
      try {
        const parsed = JSON.parse(metadata);
        if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
          errors.push(["metadata_json", "Metadata ต้องเป็น JSON object"]);
        }
      } catch (_error) {
        errors.push(["metadata_json", "Metadata ต้องเป็น JSON ที่ถูกต้อง"]);
      }
    }

    errors.forEach(([name, message]) => showFieldError(form, name, message));
    if (errors.length) {
      form.querySelector(".has-error input, .has-error textarea, .has-error select")?.focus();
    }
    return errors.length === 0;
  }

  function bindVideoFormValidation(form) {
    form.addEventListener("submit", function (event) {
      if (!validateVideoForm(form)) {
        event.preventDefault();
      }
    });
  }

  function bindLoadingState(form) {
    form.addEventListener("submit", function (event) {
      if (event.defaultPrevented) {
        return;
      }

      const submitButton = form.querySelector("button[type='submit']");
      if (!submitButton || submitButton.disabled) {
        return;
      }

      submitButton.dataset.originalText = submitButton.textContent;
      submitButton.textContent = "กำลังทำงาน...";
      submitButton.disabled = true;
      form.classList.add("is-submitting");
    });
  }

  function ensureUploadErrorElement(panel) {
    let errorElement = panel.querySelector(".upload-error");
    if (!errorElement) {
      errorElement = document.createElement("div");
      errorElement.className = "upload-error is-hidden";
      panel.appendChild(errorElement);
    }
    return errorElement;
  }

  function ensureUploadResultElement(panel) {
    let resultElement = panel.querySelector(".upload-result");
    if (!resultElement) {
      resultElement = document.createElement("details");
      resultElement.className = "upload-result is-hidden";

      const summary = document.createElement("summary");
      summary.textContent = "ดูผลลัพธ์ล่าสุดจาก Upload API";

      const pre = document.createElement("pre");
      resultElement.append(summary, pre);
      panel.appendChild(resultElement);
    }
    return resultElement;
  }

  function updateUploadPanel(panel, item) {
    if (!panel || !item) {
      return;
    }

    const uploadStateElement = panel.querySelector(".upload-state");
    const uploadJobIdElement = panel.querySelector(".upload-panel-head strong");
    const uploadedAtElement = panel.querySelector(".upload-meta-grid strong");
    const errorElement = ensureUploadErrorElement(panel);
    const resultElement = ensureUploadResultElement(panel);
    const resultPreElement = resultElement.querySelector("pre");

    panel.dataset.uploadJobId = item.upload_job_id ? String(item.upload_job_id) : "";

    if (uploadJobIdElement) {
      uploadJobIdElement.textContent = item.upload_job_id || "ยังไม่ส่ง";
    }

    if (uploadedAtElement) {
      uploadedAtElement.textContent = item.uploaded_at_display || "-";
    }

    if (uploadStateElement) {
      uploadStateElement.textContent = item.upload_status || "not_sent";
      Array.from(uploadStateElement.classList)
        .filter((className) => className.startsWith("upload-state-"))
        .forEach((className) => uploadStateElement.classList.remove(className));
      uploadStateElement.classList.add(normalizeUploadStateClass(item.upload_status));
    }

    if (item.last_error) {
      errorElement.textContent = item.last_error;
      errorElement.classList.remove("is-hidden");
    } else {
      errorElement.textContent = "";
      errorElement.classList.add("is-hidden");
    }

    if (item.result && Object.keys(item.result).length > 0) {
      resultPreElement.textContent = item.result_pretty || "{}";
      resultElement.classList.remove("is-hidden");
    } else {
      resultPreElement.textContent = "";
      resultElement.classList.add("is-hidden");
    }
  }

  async function refreshUploadPanel(panel) {
    const videoId = panel?.dataset.videoId;
    const uploadJobId = panel?.dataset.uploadJobId;

    if (!videoId || !uploadJobId || document.hidden) {
      return;
    }

    try {
      const response = await fetch(`/videos/${videoId}/refresh-upload-status`, {
        method: "POST",
        headers: {
          Accept: "application/json",
        },
      });

      const payload = await response.json();
      if (!response.ok || !payload.success) {
        throw new Error(payload.message || `HTTP ${response.status}`);
      }

      updateUploadPanel(panel, payload.item);
    } catch (_error) {
      // Keep polling quiet to avoid noisy UI when the upload API is temporarily unavailable.
    }
  }

  async function refreshUploadSummary() {
    if (!uploadSummaryValues.length || document.hidden) {
      return;
    }

    try {
      const response = await fetch("/upload-summary", {
        headers: {
          Accept: "application/json",
        },
      });

      const payload = await response.json();
      if (!response.ok || !payload.success) {
        throw new Error(payload.message || `HTTP ${response.status}`);
      }

      updateUploadSummary(payload.item);
    } catch (_error) {
      // Keep summary refresh quiet when Upload API is temporarily unavailable.
    }
  }

  function startUploadPolling() {
    if (!uploadPanels.length && !uploadSummaryValues.length) {
      return;
    }

    const tick = function () {
      uploadPanels.forEach((panel) => {
        refreshUploadPanel(panel);
      });
      refreshUploadSummary();
    };

    tick();
    window.setInterval(tick, 15000);
  }

  async function loadInlineAccounts(form, selectedAccountId) {
    const platformSelectElement = form.querySelector(".inline-platform");
    const accountSelectElement = form.querySelector(".inline-account");
    const accountHintElement = form.querySelector(".inline-account-hint");

    if (!platformSelectElement || !accountSelectElement) {
      return;
    }

    if (!platformSelectElement.value) {
      populateSelect(accountSelectElement, [], "", "เลือก Platform ก่อน");
      accountSelectElement.disabled = true;
      setInlineStatus(accountHintElement, "ยังไม่มี Platform ที่เลือก", "");
      return;
    }

    accountSelectElement.disabled = true;
    setInlineStatus(accountHintElement, "กำลังโหลด Account...", "");

    try {
      const items = await fetchReference(`/reference/device-platforms/${platformSelectElement.value}/accounts`);
      populateSelect(accountSelectElement, items, selectedAccountId, "ไม่พบ Account");
      accountSelectElement.disabled = !items.length;
      setInlineStatus(accountHintElement, `${items.length} รายการสำหรับ Platform นี้`, "");
    } catch (error) {
      populateSelect(accountSelectElement, [], "", "โหลด Account ไม่สำเร็จ");
      accountSelectElement.disabled = true;
      setInlineStatus(accountHintElement, `โหลด Account ไม่สำเร็จ: ${error.message}`, "is-error");
    }
  }

  async function loadInlinePlatforms(form, selectedPlatformId, selectedAccountId) {
    const deviceSelectElement = form.querySelector(".inline-device");
    const platformSelectElement = form.querySelector(".inline-platform");
    const accountSelectElement = form.querySelector(".inline-account");
    const platformHintElement = form.querySelector(".inline-platform-hint");
    const accountHintElement = form.querySelector(".inline-account-hint");

    if (!deviceSelectElement || !platformSelectElement || !accountSelectElement) {
      return;
    }

    if (!deviceSelectElement.value) {
      populateSelect(platformSelectElement, [], "", "เลือก Device ก่อน");
      populateSelect(accountSelectElement, [], "", "เลือก Platform ก่อน");
      platformSelectElement.disabled = true;
      accountSelectElement.disabled = true;
      setInlineStatus(platformHintElement, "ยังไม่มี Device ที่เลือก", "");
      setInlineStatus(accountHintElement, "ยังไม่มี Platform ที่เลือก", "");
      return;
    }

    platformSelectElement.disabled = true;
    accountSelectElement.disabled = true;
    setInlineStatus(platformHintElement, "กำลังโหลด Platform...", "");

    try {
      const items = await fetchReference(`/reference/devices/${deviceSelectElement.value}/platforms`);
      populateSelect(platformSelectElement, items, selectedPlatformId, "ไม่พบ Platform");
      platformSelectElement.disabled = !items.length;
      setInlineStatus(platformHintElement, `${items.length} รายการสำหรับ Device นี้`, "");
      await loadInlineAccounts(form, selectedAccountId);
    } catch (error) {
      populateSelect(platformSelectElement, [], "", "โหลด Platform ไม่สำเร็จ");
      populateSelect(accountSelectElement, [], "", "โหลด Account ไม่สำเร็จ");
      platformSelectElement.disabled = true;
      accountSelectElement.disabled = true;
      setInlineStatus(platformHintElement, `โหลด Platform ไม่สำเร็จ: ${error.message}`, "is-error");
      setInlineStatus(accountHintElement, "ยังโหลด Account ไม่ได้", "is-error");
    }
  }

  function bindInlineReferenceForm(form) {
    const card = form.closest(".video-card");
    const deviceSelectElement = form.querySelector(".inline-device");
    const platformSelectElement = form.querySelector(".inline-platform");
    const accountSelectElement = form.querySelector(".inline-account");
    const workflowSelectElement = form.querySelector(".inline-workflow");
    const saveStatusElement = form.querySelector(".inline-save-status");
    const saveButton = form.querySelector(".inline-save-button");
    const updatedAtElement = card?.querySelector(".time-stamp strong");

    if (!deviceSelectElement || !platformSelectElement || !accountSelectElement || !workflowSelectElement) {
      return;
    }

    deviceSelectElement.addEventListener("change", function () {
      loadInlinePlatforms(form, "", "");
    });

    platformSelectElement.addEventListener("change", function () {
      loadInlineAccounts(form, "");
    });

    form.addEventListener("submit", async function (event) {
      event.preventDefault();

      const payload = {
        device_id: Number(deviceSelectElement.value),
        device_platform_id: Number(platformSelectElement.value),
        account_id: Number(accountSelectElement.value),
        workflow_id: Number(workflowSelectElement.value),
      };

      saveButton.disabled = true;
      setInlineStatus(saveStatusElement, "กำลังบันทึก...", "");

      try {
        const response = await fetch(form.action, {
          method: "POST",
          headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
          },
          body: JSON.stringify(payload),
        });

        const result = await response.json();
        if (!response.ok || !result.success) {
          throw new Error(result.message || `HTTP ${response.status}`);
        }

        refreshCardSearch(card, form);

        if (updatedAtElement && result.item?.updated_at_display) {
          updatedAtElement.textContent = result.item.updated_at_display;
        }

        setInlineStatus(saveStatusElement, result.message || "บันทึกสำเร็จ", "is-success");
      } catch (error) {
        setInlineStatus(saveStatusElement, `บันทึกไม่สำเร็จ: ${error.message}`, "is-error");
      } finally {
        saveButton.disabled = false;
      }
    });

    loadInlinePlatforms(
      form,
      platformSelectElement.dataset.selected || platformSelectElement.value,
      accountSelectElement.dataset.selected || accountSelectElement.value
    );
  }

  if (openCreateModalButton) {
    openCreateModalButton.addEventListener("click", openModal);
  }

  closeModalButtons.forEach((button) => {
    button.addEventListener("click", closeModal);
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && modal?.classList.contains("is-open")) {
      closeModal();
    }
  });

  if (deviceSelect && platformSelect && accountSelect) {
    deviceSelect.addEventListener("change", function () {
      loadPlatforms("", "");
    });

    platformSelect.addEventListener("change", function () {
      loadAccounts("");
    });

    loadPlatforms(platformSelect.dataset.selected || platformSelect.value, accountSelect.dataset.selected || accountSelect.value);
  }

  if (modal?.classList.contains("is-open")) {
    body.classList.add("modal-active");
  }

  inlineReferenceForms.forEach(bindInlineReferenceForm);
  videoForms.forEach(bindVideoFormValidation);
  actionForms.forEach(bindLoadingState);

  startUploadPolling();
})();
