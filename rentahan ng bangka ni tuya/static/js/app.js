document.addEventListener("DOMContentLoaded", function () {
  const previewModalEl = document.getElementById("imagePreviewModal");
  if (previewModalEl) {
    const previewModal = new bootstrap.Modal(previewModalEl);
    const previewImage = document.getElementById("previewImage");
    const previewTitle = document.getElementById("previewTitle");

    document.querySelectorAll(".preview-trigger").forEach((img) => {
      img.addEventListener("click", () => {
        previewImage.src = img.src;
        previewTitle.textContent = img.dataset.title || "Image Preview";
        previewModal.show();
      });
    });
  }

  const paymentMethod = document.getElementById("paymentMethod");
  const gcashModalEl = document.getElementById("gcashModal");
  const gcashReceiptInput = document.querySelector('input[name="gcash_receipt"]');
  if (paymentMethod && gcashModalEl) {
    const gcashModal = new bootstrap.Modal(gcashModalEl);
    paymentMethod.addEventListener("change", () => {
      if (paymentMethod.value === "gcash") {
        gcashModal.show();
        if (gcashReceiptInput) gcashReceiptInput.required = true;
      } else if (gcashReceiptInput) {
        gcashReceiptInput.required = false;
      }
    });
    if (gcashReceiptInput) {
      gcashReceiptInput.required = paymentMethod.value === "gcash";
    }
  }

  const chatSearchInput = document.getElementById("chatSearchInput");
  if (chatSearchInput) {
    const conversationItems = document.querySelectorAll(".conversation-item");
    chatSearchInput.addEventListener("input", () => {
      const query = chatSearchInput.value.trim().toLowerCase();
      conversationItems.forEach((item) => {
        const name = item.dataset.contactName || "";
        item.style.display = name.includes(query) ? "flex" : "none";
      });
    });
  }

  const chatRealtimeRoot = document.getElementById("chatRealtimeRoot");
  const chatInput = document.querySelector('.chat-input input[name="content"]');
  const liveClock = document.getElementById("liveClock");
  if (liveClock) {
    const tick = () => {
      liveClock.textContent = new Date().toLocaleTimeString();
    };
    tick();
    setInterval(tick, 1000);
  }
  if (chatRealtimeRoot) {
    setInterval(() => {
      if (document.hidden) return;
      if (chatInput && document.activeElement === chatInput) return;
      window.location.reload();
    }, 5000);
  }

  const emojiBtn = document.getElementById("emojiBtn");
  const chatTextInput = document.querySelector('.chat-input input[name="content"]');
  const emojiPanel = document.getElementById("emojiPanel");
  if (emojiBtn && chatTextInput && emojiPanel) {
    const emojis = [
      "😀", "😁", "😂", "🤣", "😊", "😍", "😘", "😎",
      "🤩", "😢", "😭", "😡", "👍", "👏", "🙏", "🔥",
      "❤️", "💙", "💚", "💛", "🎉", "✨", "😅", "🤗",
      "😴", "🤔", "🙌", "👌", "🤝", "💯", "🥰", "🤍"
    ];
    emojiPanel.innerHTML = emojis
      .map((e) => `<button type="button" class="emoji-item" data-emoji="${e}">${e}</button>`)
      .join("");

    emojiBtn.addEventListener("click", () => {
      emojiPanel.classList.toggle("d-none");
    });

    emojiPanel.querySelectorAll(".emoji-item").forEach((btn) => {
      btn.addEventListener("click", () => {
        chatTextInput.value += btn.dataset.emoji;
        chatTextInput.focus();
      });
    });

    document.addEventListener("click", (e) => {
      if (!emojiPanel.contains(e.target) && e.target !== emojiBtn) {
        emojiPanel.classList.add("d-none");
      }
    });
  }
});
