package dev.msemitkin.stravacalendar.config;

import software.amazon.awssdk.services.ssm.SsmClient;
import software.amazon.awssdk.services.ssm.model.GetParametersByPathRequest;
import java.util.HashMap;
import java.util.Map;

public final class Parameters {
    private final SsmClient ssm = SsmClient.create();
    private final String prefix = System.getenv().getOrDefault("PARAMETER_PREFIX", "/strava-calendar-sync");

    public Map<String, String> load() {
        var values = new HashMap<String, String>();
        String token = null;
        do {
            var response = ssm.getParametersByPath(GetParametersByPathRequest.builder()
                    .path(prefix + "/").withDecryption(true).recursive(false).nextToken(token).build());
            response.parameters().forEach(p -> values.put(p.name().substring(prefix.length() + 1), p.value()));
            token = response.nextToken();
        } while (token != null);
        return values;
    }
}

