// Show / hide password
document.querySelectorAll("[data-toggle-password]").forEach(function (btn) {
  btn.addEventListener("click", function () {
    var input = document.getElementById(btn.getAttribute("data-toggle-password"));
    if (!input) return;
    var show = input.type === "password";
    input.type = show ? "text" : "password";
    btn.setAttribute("aria-label", show ? "Hide password" : "Show password");
    btn.style.color = show ? "#0b6df0" : "";
  });
});

// Registration: quick checks before sending (the server checks again)
var form = document.querySelector("[data-register-form]");
if (form) {
  form.addEventListener("submit", function (e) {
    var pw = form.elements["password"].value;
    var confirm = form.elements["confirm_password"].value;
    var msg = "";
    if (pw.length < 8 || !/[A-Za-z]/.test(pw) || !/\d/.test(pw)) {
      msg = "Password must be at least 8 characters and contain a letter and a number.";
    } else if (pw !== confirm) {
      msg = "Passwords do not match.";
    }
    var box = form.querySelector(".client-alert");
    if (msg) {
      e.preventDefault();
      if (!box) {
        box = document.createElement("div");
        box.className = "alert alert-error client-alert";
        box.setAttribute("role", "alert");
        form.insertBefore(box, form.firstChild.nextSibling);
      }
      box.textContent = msg;
      box.scrollIntoView({ block: "center" });
    }
  });
}

// Stop double clicks on submit buttons
document.querySelectorAll("form").forEach(function (f) {
  f.addEventListener("submit", function (e) {
    if (e.defaultPrevented) return;
    var b = f.querySelector('button[type="submit"].btn');
    if (b) { b.disabled = true; }
  });
});
