// Redirect cajera and admin to /desk/desktop on first page load after login
(function () {
	function check_and_redirect() {
		if (!frappe.boot || !frappe.boot.desktop_redirect) return;

		var path = window.location.pathname;
		var hash = window.location.hash || "";

		// Already on desktop - don't redirect
		if (path.indexOf("/desk/desktop") !== -1) return;

		// Only redirect from workspace landing pages
		var is_landing =
			path.indexOf("/app/home") !== -1 ||
			path.indexOf("/app/cajero") !== -1 ||
			path.indexOf("/app/invoicing") !== -1 ||
			path.indexOf("/desk/cajero") !== -1 ||
			path.indexOf("/desk/invoicing") !== -1 ||
			(path.indexOf("/app") !== -1 && (hash.indexOf("cajero") !== -1 || hash.indexOf("invoicing") !== -1 || hash.indexOf("home") !== -1));

		if (!is_landing) return;

		// Only redirect once per session
		if (sessionStorage.getItem("desktop_redirected")) return;
		sessionStorage.setItem("desktop_redirected", "1");

		window.location.href = frappe.boot.desktop_redirect;
	}

	// Try multiple hooks to ensure it runs
	// 1. After Frappe boot is ready
	$(document).on("boot", function () {
		setTimeout(check_and_redirect, 100);
	});

	// 2. After AJAX (fallback)
	if (frappe.after_ajax) {
		frappe.after_ajax(function () {
			setTimeout(check_and_redirect, 200);
		});
	}

	// 3. On route change (fallback)
	$(document).on("page-change", function () {
		setTimeout(check_and_redirect, 300);
	});

	// 4. Simple timeout (last resort)
	setTimeout(function () {
		if (frappe.boot) check_and_redirect();
	}, 1000);
})();
