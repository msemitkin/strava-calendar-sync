package dev.msemitkin.stravacalendar.model;

import java.time.Instant;

public record StravaActivity(long id, String name, String sportType, Instant startDate,
                             int elapsedTime, double distance, double totalElevationGain,
                             boolean isPrivate, String description) {}

