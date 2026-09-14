package com.blackwallghost.cyberpunkcatalog

import android.content.Context
import android.os.Bundle
import org.json.JSONArray
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Card
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

private enum class SortOption(val label: String) {
    CARD_NUMBER_ASC("Card # ↑"),
    CARD_NUMBER_DESC("Card # ↓"),
    NAME_ASC("Name A–Z"),
    NAME_DESC("Name Z–A"),
    RARITY("Rarity")
}

data class CardPrinting(
    val id: String,
    val name: String,
    val subtitle: String,
    val setName: String,
    val collectorNumber: String,
    val rarity: String,
    val type: String
)

private val officialSeedCatalog = listOf(
    CardPrinting("wtnc-beta-168", "Johnny Silverhand", "Rocking Renegade", "Welcome to Night City — Beta", "β168", "Secret", "Legend"),
    CardPrinting("wtnc-retail-003", "Johnny Silverhand", "Rocking Renegade", "Welcome to Night City — Retail", "003", "Secret", "Legend"),
    CardPrinting("wtnc-beta-167", "Towerfall", "", "Welcome to Night City — Beta", "β167", "Epic", "Program"),
    CardPrinting("wtnc-retail-138", "Towerfall", "", "Welcome to Night City — Retail", "138", "Epic", "Program"),
    CardPrinting("wtnc-beta-025", "Mantis Blades", "", "Welcome to Night City — Beta", "β025", "Common", "Gear"),
    CardPrinting("wtnc-retail-025", "Mantis Blades", "", "Welcome to Night City — Retail", "025", "Common", "Gear"),
    CardPrinting("wtnc-beta-026", "Satori", "Sword of Saburo", "Welcome to Night City — Beta", "β026", "Uncommon", "Gear"),
    CardPrinting("wtnc-retail-026", "Satori", "Sword of Saburo", "Welcome to Night City — Retail", "026", "Uncommon", "Gear"),
    CardPrinting("wtnc-retail-001", "Adam Smasher", "Ender of Legends", "Welcome to Night City — Retail", "001", "Epic", "Legend"),
    CardPrinting("wtnc-retail-046", "Hanako Arasaka", "In a Gilded Cage", "Welcome to Night City — Retail", "046", "Rare", "Unit"),
    CardPrinting("wtnc-retail-123", "Placide", "Voodoo Sentinel", "Welcome to Night City — Retail", "123", "Rare", "Unit"),
    CardPrinting("wtnc-retail-128", "Dying Night", "V's Pistol", "Welcome to Night City — Retail", "128", "Rare", "Gear")
)

class CollectionStore(context: Context) {
    private val prefs = context.getSharedPreferences("collection", Context.MODE_PRIVATE)

    fun quantity(cardId: String): Int = prefs.getInt(cardId, 0)

    fun setQuantity(cardId: String, quantity: Int) {
        prefs.edit().putInt(cardId, quantity.coerceAtLeast(0)).apply()
    }
}

private fun loadCatalog(context: Context): List<CardPrinting> = runCatching {
    val json = context.assets.open("catalog.json").bufferedReader().use { it.readText() }
    val array = JSONArray(json)
    List(array.length()) { index ->
        val item = array.getJSONObject(index)
        CardPrinting(
            id = item.getString("id"),
            name = item.getString("name"),
            subtitle = item.optString("subtitle"),
            setName = item.getString("setName"),
            collectorNumber = item.getString("collectorNumber"),
            rarity = item.getString("rarity"),
            type = item.getString("type")
        )
    }
}.getOrElse { officialSeedCatalog }

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val store = CollectionStore(this)
        setContent { CyberpunkCatalogApp(store, loadCatalog(this)) }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CyberpunkCatalogApp(store: CollectionStore, catalog: List<CardPrinting>) {
    var query by remember { mutableStateOf("") }
    var rarity by remember { mutableStateOf("All") }
    var edition by remember { mutableStateOf("All") }
    var sortOption by remember { mutableStateOf(SortOption.CARD_NUMBER_ASC) }
    var sortMenuExpanded by remember { mutableStateOf(false) }
    var ownedOnly by remember { mutableStateOf(false) }
    var refreshKey by remember { mutableStateOf(0) }

    val rarities = listOf("All", "Common", "Uncommon", "Rare", "Epic", "Secret")
    val editions = listOf("All", "Retail", "Beta")
    val rarityRank = mapOf("Common" to 0, "Uncommon" to 1, "Rare" to 2, "Epic" to 3, "Secret" to 4)
    val cards = remember(query, rarity, edition, sortOption, ownedOnly, refreshKey) {
        catalog.filter { card ->
            val searchable = listOf(
                card.name, card.subtitle, card.collectorNumber,
                card.setName, card.rarity, card.type
            ).joinToString(" ").lowercase()
            val matchesQuery = query.isBlank() || searchable.contains(query.trim().lowercase())
            val cardEdition = if (
                card.collectorNumber.startsWith("β", ignoreCase = true) ||
                card.id.contains("-beta-", ignoreCase = true) ||
                card.setName.contains("Beta", ignoreCase = true)
            ) "Beta" else "Retail"
            val matchesRarity = rarity == "All" || card.rarity == rarity
            val matchesEdition = edition == "All" || cardEdition == edition
            val matchesOwned = !ownedOnly || store.quantity(card.id) > 0
            matchesQuery && matchesRarity && matchesEdition && matchesOwned
        }.sortedWith(
            when (sortOption) {
                SortOption.CARD_NUMBER_ASC -> compareBy<CardPrinting>({ collectorNumberValue(it) }, { editionValue(it) }, { it.name.lowercase() })
                SortOption.CARD_NUMBER_DESC -> compareByDescending<CardPrinting> { collectorNumberValue(it) }
                    .thenBy { editionValue(it) }
                    .thenBy { it.name.lowercase() }
                SortOption.NAME_ASC -> compareBy<CardPrinting>({ it.name.lowercase() }, { collectorNumberValue(it) })
                SortOption.NAME_DESC -> compareByDescending<CardPrinting> { it.name.lowercase() }
                    .thenBy { collectorNumberValue(it) }
                SortOption.RARITY -> compareBy<CardPrinting>({ rarityRank[it.rarity] ?: Int.MAX_VALUE }, { collectorNumberValue(it) })
            }
        )
    }

    MaterialTheme {
        Scaffold(topBar = { TopAppBar(title = { Text("Cyberpunk Catalog") }) }) { padding ->
            Column(
                modifier = Modifier.fillMaxSize().padding(padding).padding(horizontal = 12.dp)
            ) {
                OutlinedTextField(
                    value = query,
                    onValueChange = { query = it },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("Search cards or numbers") },
                    singleLine = true
                )
                Spacer(Modifier.height(8.dp))
                Row(
                    modifier = Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()),
                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    rarities.forEach { option ->
                        FilterChip(
                            selected = rarity == option,
                            onClick = { rarity = option },
                            label = { Text(option) }
                        )
                    }
                }
                Row(
                    modifier = Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()),
                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    editions.forEach { option ->
                        FilterChip(
                            selected = edition == option,
                            onClick = { edition = option },
                            label = { Text(option) }
                        )
                    }
                }
                Row(
                    modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    FilterChip(
                        selected = ownedOnly,
                        onClick = { ownedOnly = !ownedOnly },
                        label = { Text("Owned only") }
                    )
                    Spacer(Modifier.weight(1f))
                    Column(horizontalAlignment = Alignment.End) {
                        TextButton(onClick = { sortMenuExpanded = true }) {
                            Text("Sort: ${sortOption.label}")
                        }
                        DropdownMenu(
                            expanded = sortMenuExpanded,
                            onDismissRequest = { sortMenuExpanded = false }
                        ) {
                            SortOption.entries.forEach { option ->
                                DropdownMenuItem(
                                    text = { Text(option.label) },
                                    onClick = {
                                        sortOption = option
                                        sortMenuExpanded = false
                                    }
                                )
                            }
                        }
                    }
                    Text(cards.size.toString() + " printings", modifier = Modifier.padding(start = 8.dp), style = MaterialTheme.typography.labelMedium)
                }
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    items(cards, key = { it.id }) { card ->
                        CardRow(card, store, onQuantityChanged = { refreshKey++ })
                    }
                }
            }
        }
    }
}

@Composable
private fun CardRow(card: CardPrinting, store: CollectionStore, onQuantityChanged: () -> Unit) {
    var quantity by remember(card.id) { mutableStateOf(store.quantity(card.id)) }

    Card(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(card.collectorNumber + "  " + card.name, fontWeight = FontWeight.Bold)
                if (card.subtitle.isNotBlank()) {
                    Text(card.subtitle, style = MaterialTheme.typography.bodyMedium)
                }
                Text(
                    card.setName.replace(" — ", " - ") + " | " + card.rarity + " | " + card.type,
                    style = MaterialTheme.typography.labelMedium
                )
            }
            IconButton(onClick = {
                quantity = (quantity - 1).coerceAtLeast(0)
                store.setQuantity(card.id, quantity)
                onQuantityChanged()
            }) {
                Text("−", style = MaterialTheme.typography.headlineSmall)
            }
            Text(quantity.toString(), modifier = Modifier.padding(horizontal = 4.dp), fontWeight = FontWeight.Bold)
            IconButton(onClick = {
                quantity += 1
                store.setQuantity(card.id, quantity)
                onQuantityChanged()
            }) {
                Text("+", style = MaterialTheme.typography.headlineSmall)
            }
        }
    }
}

private fun collectorNumberValue(card: CardPrinting): Int =
    card.collectorNumber.filter(Char::isDigit).toIntOrNull() ?: Int.MAX_VALUE

private fun editionValue(card: CardPrinting): Int =
    if (card.collectorNumber.startsWith("β") || card.id.contains("-beta-", ignoreCase = true)) 1 else 0
