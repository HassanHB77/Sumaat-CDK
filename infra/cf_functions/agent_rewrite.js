// CloudFront Function (viewer request) on the /agent/* behavior.
// The website POSTs to /agent/chat on its own address; AgentCore Runtime expects
//   POST /runtimes/<URL-encoded runtime ARN>/invocations
// on bedrock-agentcore.<region>.amazonaws.com. Anything else under /agent/ gets a 404.
// __RUNTIME_ARN__ is replaced by the real ARN when CDK builds the function (infra/web_stack.py).
var RUNTIME_ARN = "__RUNTIME_ARN__";

function handler(event) {
  var request = event.request;
  if (request.uri !== "/agent/chat" || request.method !== "POST") {
    return { statusCode: 404, statusDescription: "Not Found" };
  }
  request.uri = "/runtimes/" + encodeURIComponent(RUNTIME_ARN) + "/invocations";
  request.querystring = { qualifier: { value: "DEFAULT" } };
  return request;
}
