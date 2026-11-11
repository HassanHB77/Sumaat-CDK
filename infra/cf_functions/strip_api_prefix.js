// CloudFront Function (viewer request) on the /api/* behavior.
// The website calls /api/restaurants; API Gateway knows the route as /restaurants (under stage /prod,
// which CloudFront adds as the origin path). So remove the leading "/api".
//   /api/orders/mine -> /orders/mine
//   /api             -> /
// Query strings are separate (event.request.querystring) and pass through untouched.
function handler(event) {
  var request = event.request;
  var uri = request.uri.replace(/^\/api(?=\/|$)/, "");
  request.uri = uri === "" ? "/" : uri;
  return request;
}
