package dev.msemitkin.stravacalendar;

import dev.msemitkin.stravacalendar.model.StravaActivity;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.util.Map;
import software.amazon.awssdk.services.ssm.SsmClient;
import software.amazon.awssdk.services.ssm.model.PutParameterRequest;

final class StravaClient {
    private final HttpClient http = HttpClient.newHttpClient();
    private final OAuthClient oauth = new OAuthClient();
    private final Map<String, String> config;
    private final SsmClient ssm = SsmClient.create();
    private final String parameterPrefix = System.getenv().getOrDefault("PARAMETER_PREFIX", "/strava-calendar-sync");
    StravaClient(Map<String, String> config) { this.config = config; }

    StravaActivity getActivity(long id) throws Exception {
        var tokens = oauth.refresh("https://www.strava.com/oauth/token", Map.of(
                "client_id", required("strava_client_id"), "client_secret", required("strava_client_secret"),
                "refresh_token", required("strava_refresh_token"), "grant_type", "refresh_token"));
        persistRotatedRefreshToken(tokens.refreshToken());
        var request = HttpRequest.newBuilder(URI.create("https://www.strava.com/api/v3/activities/" + id))
                .header("authorization", "Bearer " + tokens.accessToken()).GET().build();
        var response = http.send(request, HttpResponse.BodyHandlers.ofString());
        if (response.statusCode() / 100 != 2)
            throw new IllegalStateException("Strava API failed: " + response.statusCode());
        return Json.MAPPER.readValue(response.body(), StravaActivity.class);
    }

    private void persistRotatedRefreshToken(String refreshToken) {
        if (refreshToken == null || refreshToken.isBlank() || refreshToken.equals(config.get("strava_refresh_token"))) return;
        ssm.putParameter(PutParameterRequest.builder()
                .name(parameterPrefix + "/strava_refresh_token")
                .type("SecureString")
                .value(refreshToken)
                .overwrite(true)
                .build());
        config.put("strava_refresh_token", refreshToken);
    }

    private String required(String name) {
        var value = config.get(name);
        if (value == null || value.isBlank()) throw new IllegalStateException("Missing parameter " + name);
        return value;
    }
}
