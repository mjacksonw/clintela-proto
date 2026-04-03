package com.clintela.app.widget

import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.Context
import android.widget.RemoteViews
import com.clintela.app.R
import org.json.JSONObject

/**
 * Clintela home screen widget for Android (AppWidget).
 *
 * Displays days since surgery + next action.
 * Data is shared via SharedPreferences from the Capacitor WebView.
 *
 * Layout: clintela_widget.xml (defined in res/layout/)
 * Configuration: clintela_widget_info.xml (defined in res/xml/)
 */
class ClintelaWidget : AppWidgetProvider() {

    companion object {
        private const val PREFS_NAME = "clintela_widget_data"
        private const val DATA_KEY = "widget_json"
    }

    override fun onUpdate(
        context: Context,
        appWidgetManager: AppWidgetManager,
        appWidgetIds: IntArray
    ) {
        for (appWidgetId in appWidgetIds) {
            updateWidget(context, appWidgetManager, appWidgetId)
        }
    }

    private fun updateWidget(
        context: Context,
        appWidgetManager: AppWidgetManager,
        appWidgetId: Int
    ) {
        val views = RemoteViews(context.packageName, R.layout.clintela_widget)
        val data = loadWidgetData(context)

        // Set days since surgery
        views.setTextViewText(
            R.id.text_day_count,
            "Day ${data.daysSinceSurgery}"
        )
        views.setTextViewText(
            R.id.text_recovery_label,
            "of Recovery"
        )

        // Set next action
        if (data.nextActions.isNotEmpty()) {
            val action = data.nextActions.first()
            views.setTextViewText(R.id.text_next_action, action.title)
            views.setTextViewText(R.id.text_next_action_due, "Due in ${action.dueIn}")
        } else {
            views.setTextViewText(R.id.text_next_action, "All caught up!")
            views.setTextViewText(R.id.text_next_action_due, "")
        }

        appWidgetManager.updateAppWidget(appWidgetId, views)
    }

    private fun loadWidgetData(context: Context): WidgetData {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val jsonString = prefs.getString(DATA_KEY, null) ?: return WidgetData.placeholder()

        return try {
            val json = JSONObject(jsonString)
            val actions = mutableListOf<WidgetAction>()
            val actionsArray = json.optJSONArray("nextActions")
            if (actionsArray != null) {
                for (i in 0 until actionsArray.length()) {
                    val actionJson = actionsArray.getJSONObject(i)
                    actions.add(WidgetAction(
                        icon = actionJson.optString("icon", ""),
                        title = actionJson.optString("title", ""),
                        dueIn = actionJson.optString("dueIn", ""),
                    ))
                }
            }
            WidgetData(
                daysSinceSurgery = json.optInt("daysSinceSurgery", 0),
                totalRecoveryDays = json.optInt("totalRecoveryDays", 30),
                nextActions = actions,
            )
        } catch (e: Exception) {
            WidgetData.placeholder()
        }
    }
}

data class WidgetData(
    val daysSinceSurgery: Int,
    val totalRecoveryDays: Int,
    val nextActions: List<WidgetAction>,
) {
    companion object {
        fun placeholder() = WidgetData(
            daysSinceSurgery = 0,
            totalRecoveryDays = 30,
            nextActions = listOf(
                WidgetAction("", "Loading...", "")
            ),
        )
    }
}

data class WidgetAction(
    val icon: String,
    val title: String,
    val dueIn: String,
)
