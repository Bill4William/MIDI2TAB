plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.roborazzi)
}

// Keep in step with MyAppVersion in build/installer.iss (the release workflow checks).
val appVersion = "1.1.0"

android {
    namespace = "com.midi2tab.fretboard"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.midi2tab.fretboard"
        minSdk = 26
        targetSdk = 36
        // 1.1.0 → 10100: increases with every release so updates install over the old app.
        versionCode = appVersion.split(".").map(String::toInt).let { (a, b, c) -> a * 10000 + b * 100 + c }
        versionName = appVersion
    }

    signingConfigs {
        // One fixed keystore, committed to the repo, so every build (local or
        // CI) has the same signature and installs as an update over the last.
        // Fine for sideloading; a Play Store release needs a private key.
        create("shared") {
            storeFile = file("midi2tab-fretboard.keystore")
            storePassword = "midi2tab"
            keyAlias = "midi2tab"
            keyPassword = "midi2tab"
        }
    }

    buildTypes {
        debug {
            signingConfig = signingConfigs.getByName("shared")
        }
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"))
            signingConfig = signingConfigs.getByName("shared")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    buildFeatures {
        compose = true
    }

    lint {
        warningsAsErrors = false
        abortOnError = true
        // Dependency versions are pinned on purpose to a known-compatible set
        // (AGP 8.13 / Kotlin 2.2 / Compose BOM 2025.12); upgrade deliberately.
        disable += setOf("GradleDependency", "AndroidGradlePluginVersion", "NewerVersionAvailable")
        // Suggests renaming mipmap-anydpi-v26, but aapt2 then can't resolve the
        // adaptive launcher icon; the -v26 qualifier is required.
        disable += "ObsoleteSdkInt"
    }

    testOptions {
        // Robolectric screenshot tests need the merged resources.
        unitTests.isIncludeAndroidResources = true
    }
}

kotlin {
    compilerOptions {
        jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(platform(libs.compose.bom))
    implementation(libs.compose.ui)
    implementation(libs.compose.ui.graphics)
    implementation(libs.compose.ui.tooling.preview)
    implementation(libs.compose.material3)
    debugImplementation(libs.compose.ui.tooling)

    testImplementation(libs.junit)
    testImplementation(libs.json)
    testImplementation(libs.robolectric)
    testImplementation(libs.roborazzi)
    testImplementation(libs.roborazzi.compose)
    testImplementation(libs.androidx.test.junit)
    testImplementation(platform(libs.compose.bom))
    testImplementation(libs.compose.ui.test.junit4)
    debugImplementation(libs.compose.ui.test.manifest)
}
