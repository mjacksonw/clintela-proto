import SwiftUI

/// Onboarding flow — 4 screens with emotional arc: Trust → Confidence → Control → Momentum.
///
/// Presented on first launch or when AuthBridge detects no valid session.
/// After completion, transitions to WebView with authenticated session.
struct OnboardingView: View {
    @State private var currentPage = 0
    @State private var pushEnabled = false
    @State private var healthEnabled = false

    let onComplete: () -> Void

    var body: some View {
        ZStack {
            DesignTokens.Colors.backgroundPrimary
                .ignoresSafeArea()

            TabView(selection: $currentPage) {
                WelcomeScreen(onContinue: { currentPage = 1 })
                    .tag(0)

                PushPermissionScreen(
                    onEnable: {
                        pushEnabled = true
                        currentPage = 2
                    },
                    onSkip: { currentPage = 2 }
                )
                .tag(1)

                HealthPermissionScreen(
                    onEnable: {
                        healthEnabled = true
                        currentPage = 3
                    },
                    onSkip: { currentPage = 3 }
                )
                .tag(2)

                ReadyScreen(
                    pushEnabled: pushEnabled,
                    healthEnabled: healthEnabled,
                    onStart: onComplete
                )
                .tag(3)
            }
            .tabViewStyle(.page(indexDisplayMode: .never))
            .animation(.easeInOut(duration: 0.3), value: currentPage)

            // Progress dots
            VStack {
                Spacer()
                ProgressDots(current: currentPage, total: 4)
                    .padding(.bottom, DesignTokens.Spacing.xl)
            }
        }
    }
}

// MARK: - Screen 1: Welcome

/// "Trust" — establish brand identity and warmth.
private struct WelcomeScreen: View {
    let onContinue: () -> Void

    var body: some View {
        VStack(spacing: DesignTokens.Spacing.lg) {
            Spacer()

            // Abstract geometric illustration (teal/coral/purple overlapping shapes)
            OnboardingIllustration(style: .welcome)
                .frame(height: 200)

            Text("Welcome to Clintela")
                .font(DesignTokens.Typography.hero())
                .tracking(-0.02 * 32) // -0.02em at 32pt
                .foregroundColor(DesignTokens.Colors.textPrimary)

            Text("Your recovery companion")
                .font(DesignTokens.Typography.sectionHeader())
                .foregroundColor(DesignTokens.Colors.textSecondary)

            Spacer()

            PrimaryButton(title: "Continue", action: onContinue)
                .padding(.horizontal, DesignTokens.Spacing.lg)

            Spacer()
                .frame(height: DesignTokens.Spacing.xxl)
        }
    }
}

// MARK: - Screen 2: Push Notification Permission

/// "Confidence" — explain notifications in warm, patient-first language.
private struct PushPermissionScreen: View {
    let onEnable: () -> Void
    let onSkip: () -> Void

    var body: some View {
        VStack(spacing: DesignTokens.Spacing.lg) {
            Spacer()

            OnboardingIllustration(style: .notifications)
                .frame(height: 200)

            Text("Stay on track")
                .font(DesignTokens.Typography.screenTitle())
                .foregroundColor(DesignTokens.Colors.textPrimary)

            Text("We'll send gentle reminders for check-ins, medications, and appointments. You control what and when.")
                .font(DesignTokens.Typography.body())
                .foregroundColor(DesignTokens.Colors.textSecondary)
                .multilineTextAlignment(.center)
                .lineSpacing(6) // 1.6 line height ≈ 16 * 0.6 = ~10, but 6 extra
                .padding(.horizontal, DesignTokens.Spacing.lg)

            Spacer()

            PrimaryButton(title: "Enable Notifications", action: onEnable)
                .padding(.horizontal, DesignTokens.Spacing.lg)

            Button("Not now") {
                onSkip()
            }
            .font(DesignTokens.Typography.caption())
            .foregroundColor(DesignTokens.Colors.textSecondary)

            Spacer()
                .frame(height: DesignTokens.Spacing.xxl)
        }
    }
}

// MARK: - Screen 3: Health Data Permission

/// "Control" — explain health data sharing with privacy emphasis.
private struct HealthPermissionScreen: View {
    let onEnable: () -> Void
    let onSkip: () -> Void

    var body: some View {
        VStack(spacing: DesignTokens.Spacing.lg) {
            Spacer()

            OnboardingIllustration(style: .health)
                .frame(height: 200)

            Text("Share your health data")
                .font(DesignTokens.Typography.screenTitle())
                .foregroundColor(DesignTokens.Colors.textPrimary)

            Text("Heart rate, steps, and activity from your phone help your care team spot issues early. Your data is encrypted and only visible to your care team.")
                .font(DesignTokens.Typography.body())
                .foregroundColor(DesignTokens.Colors.textSecondary)
                .multilineTextAlignment(.center)
                .lineSpacing(6)
                .padding(.horizontal, DesignTokens.Spacing.lg)

            // Privacy badge
            HStack(spacing: DesignTokens.Spacing.sm) {
                Image(systemName: "lock.fill")
                    .font(.system(size: 12))
                    .foregroundColor(DesignTokens.Colors.accentTeal)
                Text("HIPAA Protected")
                    .font(DesignTokens.Typography.small())
                    .foregroundColor(DesignTokens.Colors.accentTeal)
            }
            .padding(.horizontal, DesignTokens.Spacing.md)
            .padding(.vertical, DesignTokens.Spacing.sm)
            .background(DesignTokens.Colors.surfaceTeal)
            .cornerRadius(DesignTokens.Radius.sm)

            Spacer()

            PrimaryButton(title: "Connect Health Data", action: onEnable)
                .padding(.horizontal, DesignTokens.Spacing.lg)

            Button("Skip for now") {
                onSkip()
            }
            .font(DesignTokens.Typography.caption())
            .foregroundColor(DesignTokens.Colors.textSecondary)

            Spacer()
                .frame(height: DesignTokens.Spacing.xxl)
        }
    }
}

// MARK: - Screen 4: Ready

/// "Momentum" — summary + transition to action.
private struct ReadyScreen: View {
    let pushEnabled: Bool
    let healthEnabled: Bool
    let onStart: () -> Void

    var body: some View {
        VStack(spacing: DesignTokens.Spacing.lg) {
            Spacer()

            OnboardingIllustration(style: .ready)
                .frame(height: 200)

            Text("You're all set")
                .font(DesignTokens.Typography.screenTitle())
                .foregroundColor(DesignTokens.Colors.textPrimary)

            // Summary checklist
            VStack(alignment: .leading, spacing: DesignTokens.Spacing.md) {
                ChecklistRow(label: "Account created", enabled: true)
                ChecklistRow(label: "Push notifications", enabled: pushEnabled)
                ChecklistRow(label: "Health data connected", enabled: healthEnabled)
            }
            .padding(.horizontal, DesignTokens.Spacing.xl)

            Spacer()

            // Coral CTA — signals transition from setup to action (per design spec)
            Button(action: onStart) {
                Text("Start Your Recovery")
                    .font(DesignTokens.Typography.bodyEmphasis())
                    .foregroundColor(.white)
                    .frame(maxWidth: .infinity)
                    .frame(height: DesignTokens.largeTouchTarget)
                    .background(DesignTokens.Colors.accentCoral)
                    .cornerRadius(DesignTokens.Radius.md)
            }
            .padding(.horizontal, DesignTokens.Spacing.lg)

            Spacer()
                .frame(height: DesignTokens.Spacing.xxl)
        }
    }
}

// MARK: - Reusable Components

/// Teal primary action button (48px height, 12px radius).
private struct PrimaryButton: View {
    let title: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Text(title)
                .font(DesignTokens.Typography.bodyEmphasis())
                .foregroundColor(.white)
                .frame(maxWidth: .infinity)
                .frame(height: DesignTokens.largeTouchTarget)
                .background(DesignTokens.Colors.accentTeal)
                .cornerRadius(DesignTokens.Radius.md)
        }
    }
}

/// Progress dots indicator.
private struct ProgressDots: View {
    let current: Int
    let total: Int

    var body: some View {
        HStack(spacing: DesignTokens.Spacing.sm) {
            ForEach(0..<total, id: \.self) { index in
                Circle()
                    .fill(index == current ? DesignTokens.Colors.accentTeal : DesignTokens.Colors.borderDefault)
                    .frame(width: 8, height: 8)
            }
        }
    }
}

/// Checklist row with checkmark or gray circle.
private struct ChecklistRow: View {
    let label: String
    let enabled: Bool

    var body: some View {
        HStack(spacing: DesignTokens.Spacing.md) {
            Image(systemName: enabled ? "checkmark.circle.fill" : "circle")
                .foregroundColor(enabled ? DesignTokens.Colors.success : DesignTokens.Colors.textTertiary)
                .font(.system(size: 20))
            Text(label)
                .font(DesignTokens.Typography.body())
                .foregroundColor(enabled ? DesignTokens.Colors.textPrimary : DesignTokens.Colors.textTertiary)
        }
    }
}

// MARK: - Illustrations

/// Abstract geometric illustrations (teal/coral/purple palette).
/// Uses SF Symbols as placeholders — replace with custom PDF vectors in production.
private struct OnboardingIllustration: View {
    enum Style {
        case welcome, notifications, health, ready
    }

    let style: Style

    var body: some View {
        ZStack {
            switch style {
            case .welcome:
                // Overlapping rounded rectangles suggesting collaboration
                RoundedRectangle(cornerRadius: 20)
                    .fill(DesignTokens.Colors.accentTeal.opacity(0.3))
                    .frame(width: 120, height: 120)
                    .offset(x: -20, y: -10)
                RoundedRectangle(cornerRadius: 20)
                    .fill(DesignTokens.Colors.accentCoral.opacity(0.3))
                    .frame(width: 100, height: 100)
                    .offset(x: 20, y: 10)
                RoundedRectangle(cornerRadius: 20)
                    .fill(DesignTokens.Colors.accentPurple.opacity(0.3))
                    .frame(width: 80, height: 80)
                    .offset(x: 0, y: -20)

            case .notifications:
                // Concentric circles from bell shape
                Circle()
                    .stroke(DesignTokens.Colors.accentTeal.opacity(0.15), lineWidth: 2)
                    .frame(width: 180, height: 180)
                Circle()
                    .stroke(DesignTokens.Colors.accentTeal.opacity(0.3), lineWidth: 2)
                    .frame(width: 130, height: 130)
                Circle()
                    .stroke(DesignTokens.Colors.accentTeal.opacity(0.5), lineWidth: 2)
                    .frame(width: 80, height: 80)
                Image(systemName: "bell.fill")
                    .font(.system(size: 32))
                    .foregroundColor(DesignTokens.Colors.accentTeal)

            case .health:
                // Heart rate sine wave + step bars
                WaveShape()
                    .stroke(
                        LinearGradient(
                            colors: [DesignTokens.Colors.accentCoral, DesignTokens.Colors.accentTeal],
                            startPoint: .leading,
                            endPoint: .trailing
                        ),
                        lineWidth: 3
                    )
                    .frame(width: 200, height: 80)

            case .ready:
                // Converging lines forming path/arrow
                Image(systemName: "arrow.right.circle.fill")
                    .font(.system(size: 64))
                    .foregroundStyle(
                        LinearGradient(
                            colors: [
                                DesignTokens.Colors.accentTeal,
                                DesignTokens.Colors.accentCoral,
                                DesignTokens.Colors.accentPurple,
                            ],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )
            }
        }
    }
}

/// Simple sine wave shape for the health illustration.
private struct WaveShape: Shape {
    func path(in rect: CGRect) -> Path {
        var path = Path()
        let midY = rect.midY
        let amplitude = rect.height * 0.4
        let wavelength = rect.width / 3

        path.move(to: CGPoint(x: 0, y: midY))

        for x in stride(from: 0, through: rect.width, by: 1) {
            let normalizedX = x / wavelength
            let y = midY + sin(normalizedX * .pi * 2) * amplitude
            path.addLine(to: CGPoint(x: x, y: y))
        }

        return path
    }
}

#Preview {
    OnboardingView(onComplete: {})
}
