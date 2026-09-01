package dev.msemitkin.stravacalendar;

import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.stream.Collectors;

final class OAuthClient {
    private final HttpClient http = HttpClient.newHttpClient();

    TokenResponse refresh(String url, Map<String, String> form) throws Exception {
        var body = form.entrySet().stream().map(e -> enc(e.getKey()) + "=" + enc(e.getValue()))
                .collect(Collectors.joining("&"));
        var request = HttpRequest.newBuilder(URI.create(url))
                .header("content-type", "application/x-www-form-urlencoded")
                .POST(HttpRequest.BodyPublishers.ofString(body)).build();
        var response = http.send(request, HttpResponse.BodyHandlers.ofString());
        if (response.statusCode() / 100 != 2)
            throw new IllegalStateException("OAuth refresh failed: " + response.statusCode());
        var json = Json.MAPPER.readTree(response.body());
        return new TokenResponse(json.path("access_token").asText(), json.path("refresh_token").asText(null));
    }

    private static String enc(String value) { return URLEncoder.encode(value, StandardCharsets.UTF_8); }

    record TokenResponse(String accessToken, String refreshToken) {}
}
