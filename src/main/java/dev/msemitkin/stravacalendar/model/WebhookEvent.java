package dev.msemitkin.stravacalendar.model;

import java.util.Map;

public record WebhookEvent(String objectType, long objectId, String aspectType,
                           long ownerId, long eventTime, Map<String, Object> updates) {}

