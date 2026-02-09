package com.bionicsailor.leakcheck

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import com.bionicsailor.leakcheck.ui.LeakCheckTheme
import com.bionicsailor.leakcheck.ui.MainScreen

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            LeakCheckTheme {
                MainScreen()
            }
        }
    }
}
