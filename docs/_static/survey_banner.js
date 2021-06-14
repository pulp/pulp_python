window.onload = function() {
    var elem = document.createElement('div');
    var body = document.getElementsByClassName("rst-content")[0]
    var doc = document.getElementsByClassName("document")[0]
    elem.className = "admonition important"
    elem.id = "pulp-survey-banner"
    elem.innerHTML = "<p>Please take our <a href=\"https://forms.gle/C3QwT9SVncXETipu9\">survey</a> to help us improve Pulp!</p>";
    body.insertBefore(elem, doc)
}
