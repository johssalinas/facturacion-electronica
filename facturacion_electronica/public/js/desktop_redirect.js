frappe.after_ajax(function () {
	if (frappe.boot && frappe.boot.desktop_redirect) {
		var current_route = frappe.get_route_str();
		var full_path = window.location.pathname + window.location.hash;

		// Only redirect if on a workspace/home page (not already on desktop or a specific doc)
		if (
			(current_route === "home" || current_route === "cajero" || current_route === "invoicing") &&
			!full_path.includes("/desk/desktop")
		) {
			// Use sessionStorage to only redirect once per session
			if (!sessionStorage.getItem("desktop_redirected")) {
				sessionStorage.setItem("desktop_redirected", "1");
				window.location.href = frappe.boot.desktop_redirect;
			}
		}
	}
});
