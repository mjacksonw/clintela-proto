import SwiftUI

/// Design tokens for Clintela native screens.
/// Matches DESIGN.md specification: Satoshi font, Teal/Coral/Purple palette.
enum DesignTokens {
    // MARK: - Colors (Light Mode)

    enum Colors {
        static let backgroundPrimary = Color(hex: 0xFAFAF9)
        static let backgroundCard = Color.white
        static let backgroundElevated = Color(hex: 0xF5F5F4)

        static let textPrimary = Color(hex: 0x1C1917)
        static let textSecondary = Color(hex: 0x78716C)
        static let textTertiary = Color(hex: 0xA8A29E)

        static let accentTeal = Color(hex: 0x0D9488)
        static let accentCoral = Color(hex: 0xEA580C)
        static let accentPurple = Color(hex: 0x7C3AED)
        static let accentBlue = Color(hex: 0x2563EB)

        static let borderDefault = Color(hex: 0xE7E5E4)
        static let borderFocus = accentTeal

        static let success = Color(hex: 0x16A34A)
        static let warning = Color(hex: 0xD97706)
        static let error = Color(hex: 0xDC2626)

        static let surfaceTeal = accentTeal.opacity(0.10)
        static let surfaceCoral = accentCoral.opacity(0.10)

        // Dark mode variants
        static let darkBackgroundPrimary = Color(hex: 0x1C1917)
        static let darkBackgroundCard = Color(hex: 0x292524)
        static let darkTextPrimary = Color(hex: 0xFAFAF9)
        static let darkTextSecondary = Color(hex: 0xA8A29E)
        static let darkAccentTeal = Color(hex: 0x2DD4BF)
        static let darkAccentCoral = Color(hex: 0xFB923C)
        static let darkBorderDefault = Color(hex: 0x44403C)
    }

    // MARK: - Typography

    /// Satoshi font family. Falls back to system font if Satoshi is not bundled.
    enum Typography {
        static func hero() -> Font {
            .custom("Satoshi-Bold", size: 32)
        }

        static func screenTitle() -> Font {
            .custom("Satoshi-SemiBold", size: 24)
        }

        static func sectionHeader() -> Font {
            .custom("Satoshi-SemiBold", size: 18)
        }

        static func body() -> Font {
            .custom("Satoshi-Regular", size: 16)
        }

        static func bodyEmphasis() -> Font {
            .custom("Satoshi-SemiBold", size: 16)
        }

        static func caption() -> Font {
            .custom("Satoshi-Regular", size: 14)
        }

        static func small() -> Font {
            .custom("Satoshi-Regular", size: 12)
        }
    }

    // MARK: - Spacing (4px base unit)

    enum Spacing {
        static let xs: CGFloat = 4
        static let sm: CGFloat = 8
        static let md: CGFloat = 16
        static let lg: CGFloat = 24
        static let xl: CGFloat = 32
        static let xxl: CGFloat = 48
    }

    // MARK: - Radius

    enum Radius {
        static let sm: CGFloat = 8
        static let md: CGFloat = 12
        static let lg: CGFloat = 16
        static let full: CGFloat = 9999
    }

    // MARK: - Touch Targets

    static let minTouchTarget: CGFloat = 44
    static let largeTouchTarget: CGFloat = 48
}

// MARK: - Color Extension for Hex

extension Color {
    init(hex: UInt, alpha: Double = 1.0) {
        self.init(
            .sRGB,
            red: Double((hex >> 16) & 0xFF) / 255,
            green: Double((hex >> 8) & 0xFF) / 255,
            blue: Double(hex & 0xFF) / 255,
            opacity: alpha
        )
    }
}
