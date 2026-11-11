// CloudFront Function (viewer request) on the website (S3) behavior.
// The React app has its own pages (/orders/123, /owner/menu ...) that are not files in S3.
// Send every path that doesn't look like a file to /index.html so a refresh or a shared link works.
//   /                 -> /index.html
//   /orders/123       -> /index.html
//   /assets/app.js    -> /assets/app.js   (has a file extension: served as is)
// Done here instead of CloudFront "error pages", which would also turn real API 404s into the website.
function handler(event) {
  var request = event.request;
  var last = request.uri.split("/").pop();
  if (last.indexOf(".") === -1) {
    request.uri = "/index.html";
  }
  return request;
}
