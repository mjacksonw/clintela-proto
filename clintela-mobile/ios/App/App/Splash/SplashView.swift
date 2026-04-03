import SwiftUI

/// Splash screen — Satoshi wordmark + teal accent line draw.
///
/// Animation sequence (0.8s total):
///   1. White/dark background appears instantly (matches system appearance)
///   2. "Clintela" wordmark fades in from 0% to 100% opacity (0–400ms, ease-out)
///   3. Teal accent line draws left-to-right beneath wordmark (200–800ms, ease-in-out)
///   4. Hold 200ms, then transition to app content
///
/// Respects Reduce Motion: instant fade, no line animation.
struct SplashView: View {
    @State private var wordmarkOpacity: Double = 0
    @State private var lineProgress: CGFloat = 0
    @State private var isFinished = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.colorScheme) private var colorScheme

    let onFinished: () -> Void

    var body: some View {
        ZStack {
            backgroundColor
                .ignoresSafeArea()

            VStack(spacing: DesignTokens.Spacing.sm) {
                // Wordmark
                Text("Clintela")
                    .font(DesignTokens.Typography.hero())
                    .tracking(-0.02 * 28)
                    .foregroundColor(wordmarkColor)
                    .opacity(wordmarkOpacity)

                // Teal accent line
                GeometryReader { geo in
                    Rectangle()
                        .fill(DesignTokens.Colors.accentTeal)
                        .frame(
                            width: geo.size.width * lineProgress,
                            height: 2
                        )
                }
                .frame(width: 140, height: 2) // Matches wordmark width approx
            }
        }
        .onAppear {
            if reduceMotion {
                // Instant show + dismiss
                wordmarkOpacity = 1
                lineProgress = 1
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
                    onFinished()
                }
            } else {
                runAnimation()
            }
        }
    }

    private var backgroundColor: Color {
        colorScheme == .dark
            ? DesignTokens.Colors.darkBackgroundPrimary
            : DesignTokens.Colors.backgroundPrimary
    }

    private var wordmarkColor: Color {
        colorScheme == .dark
            ? DesignTokens.Colors.darkTextPrimary
            : DesignTokens.Colors.textPrimary
    }

    private func runAnimation() {
        // Phase 1: Wordmark fade in (0-400ms, ease-out)
        withAnimation(.easeOut(duration: 0.4)) {
            wordmarkOpacity = 1
        }

        // Phase 2: Line draw (200-800ms, ease-in-out)
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) {
            withAnimation(.easeInOut(duration: 0.6)) {
                lineProgress = 1
            }
        }

        // Phase 3: Hold 200ms then dismiss
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
            onFinished()
        }
    }
}

#Preview {
    SplashView(onFinished: {})
}
