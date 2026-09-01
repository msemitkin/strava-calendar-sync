package dev.msemitkin.stravacalendar;

import com.amazonaws.services.lambda.runtime.Context;
import com.amazonaws.services.lambda.runtime.RequestHandler;
import com.amazonaws.services.lambda.runtime.events.APIGatewayV2HTTPEvent;
import com.amazonaws.services.lambda.runtime.events.APIGatewayV2HTTPResponse;
import dev.msemitkin.stravacalendar.model.WebhookEvent;
import software.amazon.awssdk.services.sqs.SqsClient;
import software.amazon.awssdk.services.sqs.model.SendMessageRequest;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Map;

public final class WebhookHandler implements RequestHandler<APIGatewayV2HTTPEvent, APIGatewayV2HTTPResponse> {
    private final SqsClient sqs = SqsClient.create();
    private final String queueUrl = System.getenv("QUEUE_URL");
    private final String verifyToken = System.getenv("WEBHOOK_VERIFY_TOKEN");

    @Override
    public APIGatewayV2HTTPResponse handleRequest(APIGatewayV2HTTPEvent request, Context context) {
        try {
            if ("GET".equalsIgnoreCase(request.getRequestContext().getHttp().getMethod()))
                return verify(request.getQueryStringParameters());
            var event = Json.MAPPER.readValue(request.getBody(), WebhookEvent.class);
            if ("activity".equals(event.objectType()))
                sqs.sendMessage(SendMessageRequest.builder().queueUrl(queueUrl).messageBody(request.getBody()).build());
            return response(200, "{}");
        } catch (Exception e) {
            context.getLogger().log("Webhook failure: " + e.getMessage());
            return response(500, "{\"error\":\"internal_error\"}");
        }
    }

    private APIGatewayV2HTTPResponse verify(Map<String, String> query) throws Exception {
        if (query == null || !"subscribe".equals(query.get("hub.mode")) ||
                !constantTimeEquals(verifyToken, query.get("hub.verify_token")))
            return response(403, "{\"error\":\"verification_failed\"}");
        return response(200, Json.MAPPER.writeValueAsString(Map.of("hub.challenge", query.get("hub.challenge"))));
    }

    static boolean constantTimeEquals(String expected, String actual) {
        return expected != null && actual != null && MessageDigest.isEqual(
                expected.getBytes(StandardCharsets.UTF_8), actual.getBytes(StandardCharsets.UTF_8));
    }

    private static APIGatewayV2HTTPResponse response(int status, String body) {
        return APIGatewayV2HTTPResponse.builder().withStatusCode(status)
                .withHeaders(Map.of("content-type", "application/json")).withBody(body).build();
    }
}

