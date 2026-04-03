package com.clintela.app.health

import android.content.Context
import android.util.Log
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.permission.HealthPermission
import androidx.health.connect.client.records.*
import androidx.health.connect.client.request.ReadRecordsRequest
import androidx.health.connect.client.time.TimeRangeFilter
import java.time.Instant
import java.time.temporal.ChronoUnit

/**
 * Health Connect manager — reads health data for sync to Clintela backend.
 *
 * Unlike iOS HealthKit's anchor-based queries, Health Connect uses time-range
 * based reads. We track the last sync timestamp and query from there.
 *
 * Synced data types:
 *   - Heart Rate → OMOP 3027018
 *   - Blood Pressure (systolic/diastolic) → 3004249/3012888
 *   - Weight → 3025315
 *   - Oxygen Saturation → 3016502
 *   - Body Temperature → 3020891
 *   - Steps → 40762499
 *   - Sleep → 40762503
 */
class HealthConnectManager(private val context: Context) {

    companion object {
        private const val TAG = "HealthConnect"
        private const val PREFS_NAME = "clintela_health_connect"
        private const val LAST_SYNC_KEY = "last_sync_timestamp"

        // OMOP concept ID mappings (must match apps/clinical/constants.py)
        val CONCEPT_MAP = mapOf(
            "HeartRate" to 3027018,
            "BloodPressure.systolic" to 3004249,
            "BloodPressure.diastolic" to 3012888,
            "Weight" to 3025315,
            "OxygenSaturation" to 3016502,
            "BodyTemperature" to 3020891,
            "Steps" to 40762499,
            "SleepSession" to 40762503,
        )

        /** Required Health Connect permissions. */
        val PERMISSIONS = setOf(
            HealthPermission.getReadPermission(HeartRateRecord::class),
            HealthPermission.getReadPermission(BloodPressureRecord::class),
            HealthPermission.getReadPermission(WeightRecord::class),
            HealthPermission.getReadPermission(OxygenSaturationRecord::class),
            HealthPermission.getReadPermission(BodyTemperatureRecord::class),
            HealthPermission.getReadPermission(StepsRecord::class),
            HealthPermission.getReadPermission(SleepSessionRecord::class),
        )
    }

    private val client: HealthConnectClient by lazy {
        HealthConnectClient.getOrCreate(context)
    }

    private val prefs by lazy {
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
    }

    /**
     * Check if Health Connect is available on this device.
     */
    fun isAvailable(): Boolean {
        return HealthConnectClient.getSdkStatus(context) == HealthConnectClient.SDK_AVAILABLE
    }

    /**
     * Check if all required permissions are granted.
     */
    suspend fun hasPermissions(): Boolean {
        val granted = client.permissionController.getGrantedPermissions()
        return PERMISSIONS.all { it in granted }
    }

    /**
     * Read all health data since last sync.
     * Returns a list of observation maps ready for the /api/v1/health/sync/ endpoint.
     */
    suspend fun syncAll(): List<Map<String, Any?>> {
        val lastSync = getLastSyncTimestamp()
        val now = Instant.now()
        val timeRange = TimeRangeFilter.between(lastSync, now)

        val observations = mutableListOf<Map<String, Any?>>()

        // Heart Rate
        try {
            val response = client.readRecords(
                ReadRecordsRequest(HeartRateRecord::class, timeRange)
            )
            for (record in response.records) {
                for (sample in record.samples) {
                    observations.add(mapOf(
                        "concept_id" to 3027018,
                        "value_numeric" to sample.beatsPerMinute.toDouble(),
                        "value_text" to "",
                        "unit" to "bpm",
                        "observed_at" to sample.time.toString(),
                        "source_device" to (record.metadata.dataOrigin.packageName),
                        "metadata" to null,
                    ))
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to read heart rate", e)
        }

        // Blood Pressure
        try {
            val response = client.readRecords(
                ReadRecordsRequest(BloodPressureRecord::class, timeRange)
            )
            for (record in response.records) {
                val source = record.metadata.dataOrigin.packageName
                val time = record.time.toString()
                observations.add(mapOf(
                    "concept_id" to 3004249,
                    "value_numeric" to record.systolic.inMillimetersOfMercury,
                    "value_text" to "",
                    "unit" to "mmHg",
                    "observed_at" to time,
                    "source_device" to source,
                    "metadata" to null,
                ))
                observations.add(mapOf(
                    "concept_id" to 3012888,
                    "value_numeric" to record.diastolic.inMillimetersOfMercury,
                    "value_text" to "",
                    "unit" to "mmHg",
                    "observed_at" to time,
                    "source_device" to source,
                    "metadata" to null,
                ))
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to read blood pressure", e)
        }

        // Weight
        try {
            val response = client.readRecords(
                ReadRecordsRequest(WeightRecord::class, timeRange)
            )
            for (record in response.records) {
                observations.add(mapOf(
                    "concept_id" to 3025315,
                    "value_numeric" to record.weight.inPounds,
                    "value_text" to "",
                    "unit" to "lbs",
                    "observed_at" to record.time.toString(),
                    "source_device" to record.metadata.dataOrigin.packageName,
                    "metadata" to null,
                ))
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to read weight", e)
        }

        // Oxygen Saturation
        try {
            val response = client.readRecords(
                ReadRecordsRequest(OxygenSaturationRecord::class, timeRange)
            )
            for (record in response.records) {
                observations.add(mapOf(
                    "concept_id" to 3016502,
                    "value_numeric" to record.percentage.value,
                    "value_text" to "",
                    "unit" to "%",
                    "observed_at" to record.time.toString(),
                    "source_device" to record.metadata.dataOrigin.packageName,
                    "metadata" to null,
                ))
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to read SpO2", e)
        }

        // Steps
        try {
            val response = client.readRecords(
                ReadRecordsRequest(StepsRecord::class, timeRange)
            )
            for (record in response.records) {
                observations.add(mapOf(
                    "concept_id" to 40762499,
                    "value_numeric" to record.count.toDouble(),
                    "value_text" to "",
                    "unit" to "steps",
                    "observed_at" to record.startTime.toString(),
                    "source_device" to record.metadata.dataOrigin.packageName,
                    "metadata" to null,
                ))
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to read steps", e)
        }

        // Sleep
        try {
            val response = client.readRecords(
                ReadRecordsRequest(SleepSessionRecord::class, timeRange)
            )
            for (record in response.records) {
                val durationHours = ChronoUnit.MINUTES.between(
                    record.startTime, record.endTime
                ) / 60.0
                if (durationHours > 0) {
                    observations.add(mapOf(
                        "concept_id" to 40762503,
                        "value_numeric" to durationHours,
                        "value_text" to "",
                        "unit" to "hours",
                        "observed_at" to record.startTime.toString(),
                        "source_device" to record.metadata.dataOrigin.packageName,
                        "metadata" to null,
                    ))
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to read sleep", e)
        }

        // Update last sync timestamp
        if (observations.isNotEmpty()) {
            setLastSyncTimestamp(now)
        }

        Log.i(TAG, "Synced ${observations.size} observations")
        return observations
    }

    private fun getLastSyncTimestamp(): Instant {
        val millis = prefs.getLong(LAST_SYNC_KEY, 0)
        return if (millis > 0) {
            Instant.ofEpochMilli(millis)
        } else {
            // First sync: pull last 7 days
            Instant.now().minus(7, ChronoUnit.DAYS)
        }
    }

    private fun setLastSyncTimestamp(timestamp: Instant) {
        prefs.edit().putLong(LAST_SYNC_KEY, timestamp.toEpochMilli()).apply()
    }
}
