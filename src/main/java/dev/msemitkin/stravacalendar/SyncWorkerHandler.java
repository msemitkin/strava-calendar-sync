package dev.msemitkin.stravacalendar;

import com.amazonaws.services.lambda.runtime.Context;
import com.amazonaws.services.lambda.runtime.RequestHandler;
import com.amazonaws.services.lambda.runtime.events.SQSEvent;
import dev.msemitkin.stravacalendar.config.Parameters;
import dev.msemitkin.stravacalendar.model.WebhookEvent;

public final class SyncWorkerHandler implements RequestHandler<SQSEvent, Void> {
    @Override
    public Void handleRequest(SQSEvent input, Context context) {
        var config = new Parameters().load();
        var strava = new StravaClient(config);
        var calendar = new GoogleCalendarClient(config);
        for (var record : input.getRecords()) {
            try {
                var event = Json.MAPPER.readValue(record.getBody(), WebhookEvent.class);
                if (!"activity".equals(event.objectType())) continue;
                if ("delete".equals(event.aspectType())) calendar.delete(event.objectId());
                else if ("create".equals(event.aspectType()) || "update".equals(event.aspectType()))
                    calendar.upsert(strava.getActivity(event.objectId()));
            } catch (Exception e) {
                context.getLogger().log("Sync failure for " + record.getMessageId() + ": " + e.getMessage());
                throw new RuntimeException(e);
            }
        }
        return null;
    }
}

