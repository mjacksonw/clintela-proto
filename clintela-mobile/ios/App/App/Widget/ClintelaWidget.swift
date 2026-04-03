import WidgetKit
import SwiftUI

/// Clintela home screen widget — days since surgery + next action.
///
/// Three sizes per design spec:
///   - Small (2x2): Progress ring with "Day N"
///   - Medium (4x2): Progress ring + next action card
///   - Large (4x4): Progress ring + 3 upcoming actions + last check-in
///
/// Data source: App Groups (group.com.clintela.app) shared UserDefaults.
/// Updated by the event bridge when check-ins, medications, or care plan changes occur.
/// Widget timeline: refresh every 30 minutes (WidgetKit manages actual scheduling).

// MARK: - Data Model

struct WidgetData: Codable {
    let daysSinceSurgery: Int
    let totalRecoveryDays: Int
    let nextActions: [WidgetAction]
    let lastCheckinAt: String?
    let updatedAt: String

    static let placeholder = WidgetData(
        daysSinceSurgery: 12,
        totalRecoveryDays: 30,
        nextActions: [
            WidgetAction(icon: "pill.fill", title: "Take Lisinopril", dueIn: "2 hours"),
            WidgetAction(icon: "checklist", title: "Evening check-in", dueIn: "4 hours"),
            WidgetAction(icon: "message.fill", title: "Reply to Dr. Smith", dueIn: "Today"),
        ],
        lastCheckinAt: nil,
        updatedAt: ISO8601DateFormatter().string(from: Date())
    )
}

struct WidgetAction: Codable, Identifiable {
    var id: String { title }
    let icon: String
    let title: String
    let dueIn: String
}

// MARK: - Timeline Provider

struct ClintelaTimelineProvider: TimelineProvider {
    func placeholder(in context: Context) -> ClintelaEntry {
        ClintelaEntry(date: Date(), data: .placeholder)
    }

    func getSnapshot(in context: Context, completion: @escaping (ClintelaEntry) -> Void) {
        let data = loadWidgetData()
        completion(ClintelaEntry(date: Date(), data: data))
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<ClintelaEntry>) -> Void) {
        let data = loadWidgetData()
        let entry = ClintelaEntry(date: Date(), data: data)

        // Refresh every 30 minutes
        let nextUpdate = Calendar.current.date(byAdding: .minute, value: 30, to: Date())!
        let timeline = Timeline(entries: [entry], policy: .after(nextUpdate))
        completion(timeline)
    }

    private func loadWidgetData() -> WidgetData {
        guard let defaults = UserDefaults(suiteName: "group.com.clintela.app"),
              let jsonString = defaults.string(forKey: "clintela_widget_data"),
              let data = jsonString.data(using: .utf8),
              let widgetData = try? JSONDecoder().decode(WidgetData.self, from: data)
        else {
            return .placeholder
        }
        return widgetData
    }
}

struct ClintelaEntry: TimelineEntry {
    let date: Date
    let data: WidgetData
}

// MARK: - Widget Views

/// Small widget (2x2): Teal progress ring with "Day N".
struct SmallWidgetView: View {
    let data: WidgetData

    var body: some View {
        let progress = Double(data.daysSinceSurgery) / Double(max(data.totalRecoveryDays, 1))

        ZStack {
            // Progress ring
            Circle()
                .stroke(Color(hex: 0xE7E5E4), lineWidth: 6)

            Circle()
                .trim(from: 0, to: min(progress, 1.0))
                .stroke(Color(hex: 0x0D9488), style: StrokeStyle(lineWidth: 6, lineCap: .round))
                .rotationEffect(.degrees(-90))

            VStack(spacing: 2) {
                Text("Day \(data.daysSinceSurgery)")
                    .font(.system(size: 22, weight: .bold, design: .rounded))
                    .foregroundColor(Color(hex: 0x1C1917))

                Text("of Recovery")
                    .font(.system(size: 11, weight: .regular))
                    .foregroundColor(Color(hex: 0x78716C))
            }
        }
        .padding(12)
    }
}

/// Medium widget (4x2): Progress ring + next action.
struct MediumWidgetView: View {
    let data: WidgetData

    var body: some View {
        HStack(spacing: 12) {
            // Left: progress ring
            SmallWidgetView(data: data)
                .frame(width: 100)

            // Right: next action
            if let action = data.nextActions.first {
                VStack(alignment: .leading, spacing: 4) {
                    HStack(spacing: 6) {
                        Image(systemName: action.icon)
                            .font(.system(size: 14))
                            .foregroundColor(Color(hex: 0x0D9488))
                        Text(action.title)
                            .font(.system(size: 14, weight: .semibold))
                            .foregroundColor(Color(hex: 0x1C1917))
                            .lineLimit(1)
                    }
                    Text("Due in \(action.dueIn)")
                        .font(.system(size: 12))
                        .foregroundColor(Color(hex: 0x78716C))
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            } else {
                VStack(alignment: .leading, spacing: 4) {
                    HStack(spacing: 6) {
                        Image(systemName: "checkmark.circle.fill")
                            .font(.system(size: 14))
                            .foregroundColor(Color(hex: 0x16A34A))
                        Text("All caught up!")
                            .font(.system(size: 14, weight: .semibold))
                            .foregroundColor(Color(hex: 0x1C1917))
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .padding(12)
    }
}

/// Large widget (4x4): Progress ring + 3 actions + last check-in.
struct LargeWidgetView: View {
    let data: WidgetData

    var body: some View {
        VStack(spacing: 8) {
            // Top: horizontal progress ring + day label
            HStack(spacing: 12) {
                let progress = Double(data.daysSinceSurgery) / Double(max(data.totalRecoveryDays, 1))
                ZStack {
                    Circle()
                        .stroke(Color(hex: 0xE7E5E4), lineWidth: 4)
                    Circle()
                        .trim(from: 0, to: min(progress, 1.0))
                        .stroke(Color(hex: 0x0D9488), style: StrokeStyle(lineWidth: 4, lineCap: .round))
                        .rotationEffect(.degrees(-90))
                    Text("\(data.daysSinceSurgery)")
                        .font(.system(size: 18, weight: .bold))
                        .foregroundColor(Color(hex: 0x1C1917))
                }
                .frame(width: 48, height: 48)

                Text("Day \(data.daysSinceSurgery) of Recovery")
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundColor(Color(hex: 0x1C1917))

                Spacer()
            }
            .padding(.horizontal, 4)

            Divider()

            // Middle: up to 3 actions
            ForEach(data.nextActions.prefix(3)) { action in
                HStack(spacing: 8) {
                    Image(systemName: action.icon)
                        .font(.system(size: 14))
                        .foregroundColor(Color(hex: 0x0D9488))
                        .frame(width: 20)
                    VStack(alignment: .leading, spacing: 1) {
                        Text(action.title)
                            .font(.system(size: 14, weight: .medium))
                            .foregroundColor(Color(hex: 0x1C1917))
                            .lineLimit(1)
                        Text("Due in \(action.dueIn)")
                            .font(.system(size: 11))
                            .foregroundColor(Color(hex: 0x78716C))
                    }
                    Spacer()
                }
                .padding(.horizontal, 4)
            }

            if data.nextActions.isEmpty {
                HStack(spacing: 8) {
                    Image(systemName: "checkmark.circle.fill")
                        .font(.system(size: 14))
                        .foregroundColor(Color(hex: 0x16A34A))
                    Text("All caught up!")
                        .font(.system(size: 14, weight: .medium))
                        .foregroundColor(Color(hex: 0x1C1917))
                    Spacer()
                }
                .padding(.horizontal, 4)
            }

            Spacer()

            // Bottom: staleness indicator
            if let staleness = stalenessLabel() {
                Text(staleness)
                    .font(.system(size: 11))
                    .foregroundColor(stalenessColor())
                    .frame(maxWidth: .infinity, alignment: .trailing)
                    .padding(.horizontal, 4)
            }
        }
        .padding(12)
    }

    private func stalenessLabel() -> String? {
        guard let formatter = ISO8601DateFormatter().date(from: data.updatedAt) else { return nil }
        let age = Date().timeIntervalSince(formatter)
        let hours = Int(age / 3600)
        if hours < 4 { return nil }
        return "Updated \(hours)h ago"
    }

    private func stalenessColor() -> Color {
        guard let formatter = ISO8601DateFormatter().date(from: data.updatedAt) else {
            return Color(hex: 0xA8A29E)
        }
        let age = Date().timeIntervalSince(formatter)
        return age > 86400 ? Color(hex: 0xD97706) : Color(hex: 0xA8A29E)
    }
}

// MARK: - Widget Configuration

struct ClintelaWidget: Widget {
    let kind = "ClintelaWidget"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: ClintelaTimelineProvider()) { entry in
            ClintelaWidgetEntryView(entry: entry)
                .containerBackground(.fill.tertiary, for: .widget)
        }
        .configurationDisplayName("Clintela Recovery")
        .description("Track your recovery progress and upcoming actions.")
        .supportedFamilies([.systemSmall, .systemMedium, .systemLarge])
    }
}

struct ClintelaWidgetEntryView: View {
    @Environment(\.widgetFamily) var family
    let entry: ClintelaEntry

    var body: some View {
        switch family {
        case .systemSmall:
            SmallWidgetView(data: entry.data)
        case .systemMedium:
            MediumWidgetView(data: entry.data)
        case .systemLarge:
            LargeWidgetView(data: entry.data)
        default:
            SmallWidgetView(data: entry.data)
        }
    }
}

#Preview(as: .systemSmall) {
    ClintelaWidget()
} timeline: {
    ClintelaEntry(date: Date(), data: .placeholder)
}

#Preview(as: .systemMedium) {
    ClintelaWidget()
} timeline: {
    ClintelaEntry(date: Date(), data: .placeholder)
}

#Preview(as: .systemLarge) {
    ClintelaWidget()
} timeline: {
    ClintelaEntry(date: Date(), data: .placeholder)
}
