document.addEventListener("DOMContentLoaded", () => {
  const toggle = document.getElementById("menuToggle");
  const sidebar = document.getElementById("sidebar");
  if (toggle && sidebar) {
    toggle.addEventListener("click", () => sidebar.classList.toggle("open"));
  }

  document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (!window.confirm(form.dataset.confirm)) event.preventDefault();
    });
  });

  document.querySelectorAll(".role-card").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".role-card").forEach((card) => card.classList.remove("selected"));
      button.classList.add("selected");
      const selectedRole = document.getElementById("selectedRole");
      const roleLabel = document.getElementById("roleLabel");
      if (selectedRole) selectedRole.value = button.dataset.role;
      if (roleLabel) roleLabel.textContent = button.dataset.role;
    });
  });

  window.setTimeout(() => {
    document.querySelectorAll(".flash").forEach((flash) => {
      flash.classList.add("flash-out");
      window.setTimeout(() => flash.remove(), 250);
    });
  }, 5500);
});
