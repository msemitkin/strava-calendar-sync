package dev.msemitkin.stravacalendar;

import com.fasterxml.jackson.databind.node.ObjectNode;
import dev.msemitkin.stravacalendar.model.StravaActivity;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Map;

final class GoogleCalendarClient {
    private final HttpClient http = HttpClient.newHttpClient();
    private final OAuthClient oauth = new OAuthClient();
    private final Map<String, String> config;
    GoogleCalendarClient(Map<String, String> config) { this.config = config; }

    void upsert(StravaActivity activity) throws Exception {
        var id = eventId(activity.id());
        var existing = send("GET", eventUrl(id), null);
        if (existing.statusCode() == 404) requireSuccess(send("POST", eventsUrl(), event(activity).toString()), "insert");
        else {
            requireSuccess(existing, "lookup");
            requireSuccess(send("PUT", eventUrl(id), event(activity).toString()), "update");
        }
    }

    void delete(long activityId) throws Exception {
        var response = send("DELETE", eventUrl(eventId(activityId)), null);
        if (response.statusCode() != 404 && response.statusCode() != 410) requireSuccess(response, "delete");
    }

    private ObjectNode event(StravaActivity a) {
        var root = Json.MAPPER.createObjectNode();
        root.put("id", eventId(a.id()));
        root.put("summary", emoji(a.sportType()) + " " + a.name());
        var duration = Duration.ofSeconds(a.elapsedTime());
        var text = "Strava: https://www.strava.com/activities/" + a.id() + "\n\n" +
                String.format(java.util.Locale.ROOT, "%.1f km", a.distance() / 1000) + " · " +
                "%dh %02dm".formatted(duration.toHours(), duration.toMinutesPart()) +
                (a.totalElevationGain() > 0 ? " · ↗ " + Math.round(a.totalElevationGain()) + " m" : "");
        if (a.description() != null && !a.description().isBlank()) text += "\n\n" + a.description();
        root.put("description", text);
        root.putObject("start").put("dateTime", a.startDate().toString());
        root.putObject("end").put("dateTime", a.startDate().plusSeconds(a.elapsedTime()).toString());
        root.putObject("extendedProperties").putObject("private").put("stravaActivityId", Long.toString(a.id()));
        return root;
    }

    private HttpResponse<String> send(String method, String url, String body) throws Exception {
        var token = oauth.refresh("https://oauth2.googleapis.com/token", Map.of(
                "client_id", required("google_client_id"), "client_secret", required("google_client_secret"),
                "refresh_token", required("google_refresh_token"), "grant_type", "refresh_token"));
        var builder = HttpRequest.newBuilder(URI.create(url)).header("authorization", "Bearer " + token);
        if (body != null) builder.header("content-type", "application/json");
        builder.method(method, body == null ? HttpRequest.BodyPublishers.noBody() : HttpRequest.BodyPublishers.ofString(body));
        return http.send(builder.build(), HttpResponse.BodyHandlers.ofString());
    }

    private String eventsUrl() { return "https://www.googleapis.com/calendar/v3/calendars/" + enc(required("google_calendar_id")) + "/events"; }
    private String eventUrl(String id) { return eventsUrl() + "/" + id; }
    static String eventId(long id) { return "strava" + id; }
    private static String enc(String s) { return URLEncoder.encode(s, StandardCharsets.UTF_8); }
    private String required(String name) {
        var value = config.get(name);
        if (value == null || value.isBlank()) throw new IllegalStateException("Missing parameter " + name);
        return value;
    }
    private static void requireSuccess(HttpResponse<String> r, String action) {
        if (r.statusCode() / 100 != 2)
            throw new IllegalStateException("Google Calendar " + action + " failed: " + r.statusCode() + " " + r.body());
    }
    private static String emoji(String sport) {
        if (sport == null) return "🏋️";
        return switch (sport) {
            case "Ride", "MountainBikeRide", "GravelRide", "VirtualRide" -> "🚴";
            case "Run", "TrailRun", "VirtualRun" -> "🏃";
            case "Swim" -> "🏊";
            case "Walk", "Hike" -> "🥾";
            default -> "🏋️";
        };
    }
}

