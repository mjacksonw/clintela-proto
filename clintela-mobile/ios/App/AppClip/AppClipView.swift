import SwiftUI

/// App Clip — QR-embedded token + DOB verification at discharge.
///
/// Emotional arc: Relief → Trust → Accomplishment → Continuity
///
/// Flow:
///   1. Patient scans QR code at hospital discharge desk
///   2. QR contains a time-limited single-use token + patient first name
///   3. App Clip launches → DOB verification (3-field: MM/DD/YYYY)
///   4. Token exchanged for session → first check-in survey (embedded WebView)
///   5. Post check-in → install prompt with recovery card preview
///
/// The App Clip target is a separate Xcode target sharing the DesignTokens.
/// It's intentionally lightweight (< 15MB per Apple guidelines).
struct AppClipView: View {
    @State private var currentScreen: AppClipScreen = .verify
    @State private var patientName: String = ""
    @State private var token: String = ""
    @State private var isVerified = false

    /// Injected from the QR/NFC invocation URL.
    let invocationURL: URL?

    var body: some View {
        ZStack {
            DesignTokens.Colors.backgroundPrimary
                .ignoresSafeArea()

            switch currentScreen {
            case .verify:
                VerifyScreen(
                    patientName: extractPatientName(),
                    onVerified: {
                        withAnimation { currentScreen = .verified }
                    }
                )

            case .verified:
                VerifiedScreen(
                    onStartCheckin: {
                        withAnimation { currentScreen = .checkin }
                    }
                )

            case .checkin:
                CheckinScreen(
                    token: extractToken(),
                    onComplete: {
                        withAnimation { currentScreen = .complete }
                    }
                )

            case .complete:
                CompleteScreen()
            }
        }
        .onAppear {
            parseInvocationURL()
        }
    }

    private func parseInvocationURL() {
        guard let url = invocationURL,
              let components = URLComponents(url: url, resolvingAgainstBaseURL: false)
        else { return }

        for item in components.queryItems ?? [] {
            switch item.name {
            case "token": token = item.value ?? ""
            case "name": patientName = item.value ?? ""
            default: break
            }
        }
    }

    private func extractPatientName() -> String {
        patientName.isEmpty ? "there" : patientName
    }

    private func extractToken() -> String {
        token
    }
}

private enum AppClipScreen {
    case verify, verified, checkin, complete
}

// MARK: - Screen 1: DOB Verification

/// "Relief" — patient just left the hospital. Quick, gentle identity verification.
private struct VerifyScreen: View {
    let patientName: String
    let onVerified: () -> Void

    @State private var month = ""
    @State private var day = ""
    @State private var year = ""
    @State private var error: String?
    @FocusState private var focusedField: DOBField?

    enum DOBField { case month, day, year }

    var body: some View {
        VStack(spacing: DesignTokens.Spacing.lg) {
            Spacer()

            // Wordmark (not full logo, saves space per spec)
            Text("Clintela")
                .font(DesignTokens.Typography.screenTitle())
                .foregroundColor(DesignTokens.Colors.textPrimary)

            Text("Welcome, \(patientName)")
                .font(DesignTokens.Typography.screenTitle())
                .foregroundColor(DesignTokens.Colors.textPrimary)

            Text("Verify your identity to get started")
                .font(DesignTokens.Typography.body())
                .foregroundColor(DesignTokens.Colors.textSecondary)

            // DOB entry: 3 segmented fields with large numerals, auto-advance
            HStack(spacing: DesignTokens.Spacing.md) {
                DOBField_Input(
                    placeholder: "MM",
                    text: $month,
                    maxLength: 2,
                    focused: focusedField == .month,
                    onFilled: { focusedField = .day }
                )
                .focused($focusedField, equals: .month)

                Text("/")
                    .font(.system(size: 24, weight: .light))
                    .foregroundColor(DesignTokens.Colors.textTertiary)

                DOBField_Input(
                    placeholder: "DD",
                    text: $day,
                    maxLength: 2,
                    focused: focusedField == .day,
                    onFilled: { focusedField = .year }
                )
                .focused($focusedField, equals: .day)

                Text("/")
                    .font(.system(size: 24, weight: .light))
                    .foregroundColor(DesignTokens.Colors.textTertiary)

                DOBField_Input(
                    placeholder: "YYYY",
                    text: $year,
                    maxLength: 4,
                    focused: focusedField == .year,
                    onFilled: { verifyDOB() }
                )
                .focused($focusedField, equals: .year)
            }
            .padding(.horizontal, DesignTokens.Spacing.xl)

            if let error = error {
                Text(error)
                    .font(DesignTokens.Typography.caption())
                    .foregroundColor(DesignTokens.Colors.error)
            }

            Spacer()

            Button(action: verifyDOB) {
                Text("Verify")
                    .font(DesignTokens.Typography.bodyEmphasis())
                    .foregroundColor(.white)
                    .frame(maxWidth: .infinity)
                    .frame(height: DesignTokens.largeTouchTarget)
                    .background(isFormComplete ? DesignTokens.Colors.accentTeal : DesignTokens.Colors.accentTeal.opacity(0.4))
                    .cornerRadius(DesignTokens.Radius.md)
            }
            .disabled(!isFormComplete)
            .padding(.horizontal, DesignTokens.Spacing.lg)

            Button("Having trouble?") {
                // Open help flow
            }
            .font(DesignTokens.Typography.caption())
            .foregroundColor(DesignTokens.Colors.accentBlue)

            Spacer()
                .frame(height: DesignTokens.Spacing.xl)
        }
        .onAppear { focusedField = .month }
    }

    private var isFormComplete: Bool {
        month.count == 2 && day.count == 2 && year.count == 4
    }

    private func verifyDOB() {
        guard isFormComplete else { return }
        // TODO: Call backend to verify DOB against token
        // For now, simulate success
        onVerified()
    }
}

/// Single DOB input field with auto-advance.
private struct DOBField_Input: View {
    let placeholder: String
    @Binding var text: String
    let maxLength: Int
    let focused: Bool
    let onFilled: () -> Void

    var body: some View {
        TextField(placeholder, text: $text)
            .font(.system(size: 24, weight: .medium, design: .rounded))
            .foregroundColor(DesignTokens.Colors.textPrimary)
            .multilineTextAlignment(.center)
            .keyboardType(.numberPad)
            .frame(width: maxLength == 4 ? 80 : 56, height: 56)
            .background(DesignTokens.Colors.backgroundElevated)
            .cornerRadius(DesignTokens.Radius.sm)
            .overlay(
                RoundedRectangle(cornerRadius: DesignTokens.Radius.sm)
                    .stroke(focused ? DesignTokens.Colors.borderFocus : DesignTokens.Colors.borderDefault, lineWidth: focused ? 2 : 1)
            )
            .onChange(of: text) { _, newValue in
                // Limit length and auto-advance
                if newValue.count > maxLength {
                    text = String(newValue.prefix(maxLength))
                }
                if newValue.count == maxLength {
                    onFilled()
                }
            }
    }
}

// MARK: - Screen 2: Verified

/// "Trust" — identity confirmed. Brief celebration before first check-in.
private struct VerifiedScreen: View {
    let onStartCheckin: () -> Void
    @State private var showCheckmark = false

    var body: some View {
        VStack(spacing: DesignTokens.Spacing.lg) {
            Spacer()

            // Animated checkmark
            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 64))
                .foregroundColor(DesignTokens.Colors.accentTeal)
                .scaleEffect(showCheckmark ? 1.0 : 0.5)
                .opacity(showCheckmark ? 1.0 : 0)

            Text("Identity verified")
                .font(DesignTokens.Typography.screenTitle())
                .foregroundColor(DesignTokens.Colors.textPrimary)

            Text("Let's do your first check-in. It takes about 2 minutes.")
                .font(DesignTokens.Typography.body())
                .foregroundColor(DesignTokens.Colors.textSecondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, DesignTokens.Spacing.lg)

            Spacer()

            Button(action: onStartCheckin) {
                Text("Start Check-in")
                    .font(DesignTokens.Typography.bodyEmphasis())
                    .foregroundColor(.white)
                    .frame(maxWidth: .infinity)
                    .frame(height: DesignTokens.largeTouchTarget)
                    .background(DesignTokens.Colors.accentTeal)
                    .cornerRadius(DesignTokens.Radius.md)
            }
            .padding(.horizontal, DesignTokens.Spacing.lg)

            Spacer()
                .frame(height: DesignTokens.Spacing.xxl)
        }
        .onAppear {
            withAnimation(.spring(response: 0.6, dampingFraction: 0.7)) {
                showCheckmark = true
            }
        }
    }
}

// MARK: - Screen 3: First Check-in (Embedded WebView)

/// "Accomplishment" — complete first check-in in embedded WebView.
private struct CheckinScreen: View {
    let token: String
    let onComplete: () -> Void

    var body: some View {
        VStack(spacing: 0) {
            // Native progress bar at top
            ProgressView(value: 0.2) // Updated by WebView as survey progresses
                .tint(DesignTokens.Colors.accentTeal)
                .padding(.horizontal, DesignTokens.Spacing.md)
                .padding(.top, DesignTokens.Spacing.sm)

            HStack {
                Text("1 of 5")
                    .font(DesignTokens.Typography.caption())
                    .foregroundColor(DesignTokens.Colors.textSecondary)
                Spacer()
            }
            .padding(.horizontal, DesignTokens.Spacing.md)
            .padding(.top, DesignTokens.Spacing.xs)

            // WebView placeholder — in production, this is a WKWebView
            // loading the Django check-in survey URL with the session token
            VStack {
                Spacer()
                Text("Check-in survey WebView")
                    .font(DesignTokens.Typography.body())
                    .foregroundColor(DesignTokens.Colors.textTertiary)

                // Simulate completion after 3 seconds
                Button("Complete Check-in (Demo)") {
                    onComplete()
                }
                .font(DesignTokens.Typography.bodyEmphasis())
                .foregroundColor(DesignTokens.Colors.accentTeal)
                .padding(.top, DesignTokens.Spacing.md)
                Spacer()
            }
        }
    }
}

// MARK: - Screen 4: Complete + Install Prompt

/// "Continuity" — celebrate completion, show recovery preview, prompt install.
private struct CompleteScreen: View {
    var body: some View {
        VStack(spacing: DesignTokens.Spacing.lg) {
            Spacer()

            Text("Great job!")
                .font(DesignTokens.Typography.screenTitle())
                .foregroundColor(DesignTokens.Colors.textPrimary)

            Text("Your care team has been notified.")
                .font(DesignTokens.Typography.body())
                .foregroundColor(DesignTokens.Colors.textSecondary)

            // Recovery card preview
            VStack(spacing: DesignTokens.Spacing.sm) {
                Text("Day 1 of Recovery")
                    .font(DesignTokens.Typography.bodyEmphasis())
                    .foregroundColor(DesignTokens.Colors.textPrimary)
                Text("Next: Evening medication reminder")
                    .font(DesignTokens.Typography.caption())
                    .foregroundColor(DesignTokens.Colors.textSecondary)
            }
            .padding(DesignTokens.Spacing.md)
            .frame(maxWidth: .infinity)
            .background(DesignTokens.Colors.backgroundCard)
            .cornerRadius(DesignTokens.Radius.md)
            .overlay(
                RoundedRectangle(cornerRadius: DesignTokens.Radius.md)
                    .stroke(DesignTokens.Colors.borderDefault, lineWidth: 1)
            )
            .padding(.horizontal, DesignTokens.Spacing.lg)

            Spacer()

            // Coral CTA — install full app
            Button {
                // Link to App Store
                if let url = URL(string: "https://apps.apple.com/app/clintela/id0000000000") {
                    UIApplication.shared.open(url)
                }
            } label: {
                Text("Install Clintela")
                    .font(DesignTokens.Typography.bodyEmphasis())
                    .foregroundColor(.white)
                    .frame(maxWidth: .infinity)
                    .frame(height: DesignTokens.largeTouchTarget)
                    .background(DesignTokens.Colors.accentCoral)
                    .cornerRadius(DesignTokens.Radius.md)
            }
            .padding(.horizontal, DesignTokens.Spacing.lg)

            Button("Continue in browser") {
                // Open web version
            }
            .font(DesignTokens.Typography.caption())
            .foregroundColor(DesignTokens.Colors.accentBlue)

            Spacer()
                .frame(height: DesignTokens.Spacing.xl)
        }
    }
}

#Preview {
    AppClipView(invocationURL: URL(string: "https://app.clintela.com/clip?token=abc123&name=Sarah"))
}
