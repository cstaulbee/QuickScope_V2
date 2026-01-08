# QuickScope Flow B - Cheat Sheet

## 🚀 Quick Start (30 seconds)

### Interactive Mode
```powershell
python quickstart_flow_b.py
```

### Simulation Mode (LLM Persona)
```powershell
python quickstart_flow_b.py --simulate
```

**Enter (interactive only):**
1. Process name (e.g., "Order Fulfillment")

**Done!** Start mapping.

---

## 📊 Watch Diagrams Live

1. Open VS Code
2. Install "Mermaid Preview" extension
3. Open `artifacts/live_bpmn_wf_1.mmd`
4. Right-click → "Open Preview to the Side"
5. Watch it grow as you answer! ✨

---

## 💡 Interview Tips

| Question Type | Good Answer | Bad Answer |
|---------------|-------------|------------|
| **Step description** | "Pick items from warehouse shelf" | "Pick items" |
| **Owner/role** | "Warehouse Picker" | "Someone" |
| **Inputs** | "Pick list, barcode scanner" | "Stuff" |
| **Decision** | "Is item damaged?" | "Check it" |
| **Exception** | "Item not found - notify supervisor" | "Something goes wrong" |

---

## 🎯 What Gets Captured Per Step

- Description (what happens)
- Owner/role (who does it)
- Inputs (what's needed)
- Outputs (what's produced)
- Systems/tools (software used)
- Decision point (yes/no question)
- Decision outcomes (what happens for each path)
- Wait/delay (where things pause)
- Common exception (what typically goes wrong)

---

## 🔄 Flow Structure

```
1. Enter process name
   ↓
2. Capture trigger ("What starts this?")
   ↓
3. Capture first step ("What happens first?")
   ↓
4. For each step:
   - Who does it?
   - What inputs?
   - What outputs?
   - Tools/systems?
   - Any decisions?
   - Wait/delays?
   - Common problems?
   ↓
5. Ask "What happens next?" (or type 'done')
   ↓
6. Repeat until done
   ↓
7. Capture end condition ("How do you know it's done?")
   ↓
8. Complete! Diagram auto-generated.
```

**Key insight:** You DON'T need to list all steps upfront. Just walk through them one at a time!

---

## 🐛 Common Issues

**"No diagram appearing"**
- Look for: `[DEBUG] Diagram written to: ...`
- Check: `artifacts/` folder exists
- Need: At least one committed step

**"Interview seems stuck"**
- Type `quit` to exit
- Check if waiting for your answer
- Read the question carefully

**"Want to start over"**
- Just run `python quickstart_flow_b.py` again
- Fresh session each time

---

## 📁 Output

```
artifacts/
  └── live_bpmn_wf_1.mmd    # Your workflow diagram
```

---

## 🆚 Why Not Full Flow?

| You Want | Use |
|----------|-----|
| Map process ASAP | **quickstart_flow_b.py** ✅ |
| Formal assessment | `python -m src.cli` |
| SIPOC diagram | Run Flow C after mapping |
| Get shit done | **quickstart_flow_b.py** ✅ |

---

**More info:** See `QUICKSTART_FLOW_B.md`
