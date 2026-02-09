package com.bionicsailor.leakcheck.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.bionicsailor.leakcheck.*
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

@Composable
fun BuyKeyScreen(api: ApiService) {
    val ctx = LocalContext.current
    val scope = rememberCoroutineScope()

    var plans by remember { mutableStateOf<List<Plan>>(emptyList()) }
    var selectedPlan by remember { mutableIntStateOf(0) }
    var username by remember { mutableStateOf("") }
    var creating by remember { mutableStateOf(false) }
    var order by remember { mutableStateOf<OrderResponse?>(null) }
    var statusMsg by remember { mutableStateOf("") }
    var statusColor by remember { mutableStateOf(Dim) }
    var paidKey by remember { mutableStateOf<String?>(null) }
    var polling by remember { mutableStateOf(false) }

    // Load plans
    LaunchedEffect(Unit) {
        try {
            plans = api.getPlans().plans
        } catch (_: Exception) {
            statusMsg = "Failed to load plans"; statusColor = Accent
        }
    }

    // Auto-poll order status every 15s
    LaunchedEffect(order, polling) {
        if (order != null && polling && paidKey == null) {
            while (polling) {
                delay(15_000)
                try {
                    val r = api.orderStatus(order!!.orderId ?: return@LaunchedEffect)
                    when (r.status) {
                        "paid" -> {
                            paidKey = r.apiKey; polling = false
                            statusMsg = "Payment confirmed!"; statusColor = Green
                        }
                        "expired", "cancelled" -> {
                            polling = false
                            statusMsg = "Order ${r.status}"; statusColor = Accent
                        }
                    }
                } catch (_: Exception) {}
            }
        }
    }

    Column(
        Modifier.fillMaxSize().padding(horizontal = 12.dp)
            .verticalScroll(rememberScrollState())
    ) {
        Text("Purchase Subscription Key", fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold, fontSize = 14.sp, color = Accent2)
        Text("Pay with USDT — your key is generated automatically.",
            fontFamily = FontFamily.Monospace, fontSize = 10.sp, color = Dim)

        Spacer(Modifier.height(12.dp))

        // Username
        OutlinedTextField(
            value = username, onValueChange = { username = it },
            label = { Text("Username", fontFamily = FontFamily.Monospace) },
            singleLine = true,
            modifier = Modifier.fillMaxWidth().height(56.dp),
            textStyle = LocalTextStyle.current.copy(
                fontFamily = FontFamily.Monospace, fontSize = 12.sp),
            colors = OutlinedTextFieldDefaults.colors(
                focusedBorderColor = Accent2, unfocusedBorderColor = Dim,
                focusedTextColor = FG, unfocusedTextColor = FG,
                cursorColor = Accent2,
                focusedLabelColor = Accent2, unfocusedLabelColor = Dim,
            ),
        )

        Spacer(Modifier.height(8.dp))

        // Plan selector
        if (plans.isNotEmpty()) {
            Text("Select Plan:", fontFamily = FontFamily.Monospace,
                fontSize = 11.sp, color = FG)
            Spacer(Modifier.height(4.dp))
            plans.forEachIndexed { i, plan ->
                val sel = selectedPlan == i
                Row(
                    Modifier.fillMaxWidth()
                        .background(if (sel) BG3 else BG2)
                        .clickable { selectedPlan = i }
                        .padding(12.dp, 8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    RadioButton(
                        selected = sel, onClick = { selectedPlan = i },
                        colors = RadioButtonDefaults.colors(
                            selectedColor = Accent2, unselectedColor = Dim),
                    )
                    val priceStr = "%.2f".format(plan.price)
                    Text("${plan.label}  —  ${'$'}$priceStr",
                        fontFamily = FontFamily.Monospace, fontSize = 12.sp,
                        color = if (sel) Accent2 else FG)
                }
            }
        }

        Spacer(Modifier.height(12.dp))

        // Create order
        Button(
            onClick = {
                if (plans.isEmpty()) return@Button
                creating = true; paidKey = null
                scope.launch {
                    try {
                        val r = api.createOrder(
                            OrderRequest(plans[selectedPlan].plan,
                                username.ifBlank { "user" }))
                        if (r.orderId != null) {
                            order = r; polling = true
                            statusMsg = "Order ${r.orderId} created!"; statusColor = Green
                        } else {
                            statusMsg = r.message ?: "Failed"; statusColor = Accent
                        }
                    } catch (e: Exception) {
                        statusMsg = "Error: ${friendlyError(e)}"; statusColor = Accent
                    } finally { creating = false }
                }
            },
            enabled = !creating && plans.isNotEmpty(),
            modifier = Modifier.fillMaxWidth(),
            colors = ButtonDefaults.buttonColors(containerColor = Accent),
        ) {
            Text(
                if (creating) "⏳ Creating..." else "💳 Create Order",
                fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold)
        }

        if (statusMsg.isNotBlank()) {
            Spacer(Modifier.height(6.dp))
            Text(statusMsg, fontFamily = FontFamily.Monospace,
                fontSize = 11.sp, color = statusColor)
        }

        // ── Payment info card ───────────────
        order?.let { o ->
            Spacer(Modifier.height(12.dp))
            Card(
                Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = BG2),
            ) {
                Column(Modifier.padding(14.dp)) {
                    if (paidKey != null) {
                        // ── Paid! ───────────
                        Text("PAYMENT CONFIRMED!",
                            fontFamily = FontFamily.Monospace,
                            fontWeight = FontWeight.Bold, fontSize = 14.sp, color = Green)
                        Spacer(Modifier.height(8.dp))
                        Text("Your API Key:",
                            fontFamily = FontFamily.Monospace,
                            fontSize = 11.sp, color = Dim)
                        SelectionContainer {
                            Text(paidKey!!, fontFamily = FontFamily.Monospace,
                                fontSize = 10.sp, color = Green)
                        }
                        Spacer(Modifier.height(8.dp))
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Button(
                                onClick = { copyToClipboard(ctx, paidKey!!, "API Key") },
                                colors = ButtonDefaults.buttonColors(containerColor = Accent2),
                            ) {
                                Text("📋 Copy Key", fontFamily = FontFamily.Monospace,
                                    fontSize = 11.sp, color = BG)
                            }
                            Button(
                                onClick = {
                                    Config.setApiKey(ctx, paidKey!!)
                                    statusMsg = "Key saved & activated!"; statusColor = Green
                                },
                                colors = ButtonDefaults.buttonColors(containerColor = Green),
                            ) {
                                Text("💾 Save Key", fontFamily = FontFamily.Monospace,
                                    fontSize = 11.sp, color = BG)
                            }
                        }
                    } else {
                        // ── Waiting for payment ─
                        Text("Send exactly:", fontFamily = FontFamily.Monospace,
                            fontSize = 11.sp, color = Dim)
                        val amtStr = "%.4f".format(o.amount ?: 0.0)
                        Text("${'$'}$amtStr USDT",
                            fontFamily = FontFamily.Monospace,
                            fontWeight = FontWeight.Bold, fontSize = 16.sp, color = Accent2)

                        Spacer(Modifier.height(6.dp))
                        PayInfoRow("Network", o.network ?: "TRC20")
                        PayInfoRow("Address", o.address ?: "—")
                        PayInfoRow("Order ID", o.orderId ?: "—")
                        val exp = (o.expiresAt ?: "").take(19).replace("T", " ")
                        PayInfoRow("Expires", "$exp UTC")

                        Spacer(Modifier.height(8.dp))
                        Text("⏳ Waiting for payment...",
                            fontFamily = FontFamily.Monospace,
                            fontSize = 11.sp, color = Yellow)

                        Spacer(Modifier.height(8.dp))
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Button(
                                onClick = {
                                    o.address?.let { copyToClipboard(ctx, it, "Address") }
                                },
                                colors = ButtonDefaults.buttonColors(containerColor = BG3),
                            ) {
                                Text("📋 Address", fontFamily = FontFamily.Monospace,
                                    fontSize = 10.sp)
                            }
                            Button(
                                onClick = {
                                    o.amount?.let {
                                        copyToClipboard(ctx, "%.4f".format(it), "Amount")
                                    }
                                },
                                colors = ButtonDefaults.buttonColors(containerColor = BG3),
                            ) {
                                Text("📋 Amount", fontFamily = FontFamily.Monospace,
                                    fontSize = 10.sp)
                            }
                            Button(
                                onClick = {
                                    scope.launch {
                                        try {
                                            val r = api.orderStatus(o.orderId!!)
                                            if (r.status == "paid") {
                                                paidKey = r.apiKey; polling = false
                                                statusMsg = "Payment confirmed!"
                                                statusColor = Green
                                            } else {
                                                statusMsg = "Still waiting..."
                                                statusColor = Dim
                                            }
                                        } catch (_: Exception) {
                                            statusMsg = "Check failed"; statusColor = Accent
                                        }
                                    }
                                },
                                colors = ButtonDefaults.buttonColors(containerColor = BG3),
                            ) {
                                Text("🔄 Check", fontFamily = FontFamily.Monospace,
                                    fontSize = 10.sp)
                            }
                        }
                    }
                }
            }
        }

        Spacer(Modifier.height(16.dp))
    }
}

@Composable
private fun PayInfoRow(label: String, value: String) {
    Row(Modifier.fillMaxWidth().padding(vertical = 2.dp)) {
        Text("$label: ", fontFamily = FontFamily.Monospace,
            fontSize = 11.sp, color = Dim)
        SelectionContainer {
            Text(value, fontFamily = FontFamily.Monospace,
                fontSize = 11.sp, color = Accent2)
        }
    }
}
