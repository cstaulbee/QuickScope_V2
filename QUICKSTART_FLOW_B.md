# QuickScope Flow B Quick-Start

**Skip the SIPOC intake and go straight to detailed process mapping with live diagrams!**

## 🚀 Usage

### Interactive Mode (Human User)
```powershell
python quickstart_flow_b.py
```

### Simulation Mode (LLM Persona)
```powershell
# Use default persona
python quickstart_flow_b.py --simulate

# Use specific persona and settings
python quickstart_flow_b.py --simulate --persona 1031_exchange_ops --model gpt-4o --temperature 0.7 --max-turns 200
```

**Available Personas:**
- `1031_exchange_ops` - 1031 Exchange Operations Manager (default)
- (Add more personas in `src/simulations/personas.py`)

## 🤖 Why Use Simulation Mode?

**Perfect for:**
- 🧪 **Testing changes** - Run interviews without manual input
- 📊 **Generating samples** - Create example workflows/diagrams
- 🐛 **Debugging flows** - Identify issues in interview logic
- 📚 **Documentation** - Generate realistic examples automatically
- ⚡ **Speed** - Complete a full interview in ~2 minutes vs 20+ minutes

**Example Output:**
```
Bot: What is the trigger event that starts this specific example?
User (1031_exchange_ops): Client submits 1031 exchange intent form
Bot: What specific conditions must be in place before this process can start?
User (1031_exchange_ops): Client has signed purchase agreement and IRS 45-day deadline is tracked
```

The LLM persona responds authentically based on its knowledge of the role and process!

---

## 📋 What It Does

1. **Asks 1 quick question:**
   - Process name (e.g., "Order Fulfillment")

2. **Starts detailed step-by-step mapping:**
   - Captures workflow trigger and start conditions
   - Maps each step with:
     - Description
     - Owner/role
     - Inputs & outputs
     - Systems/tools used
     - Decisions (with outcomes)
     - Wait states
     - Common exceptions

3. **Generates live BPMN diagrams:**
   - Updates after each step is captured
   - Written to `artifacts/live_bpmn_wf_1.mmd`
   - View in VS Code with Mermaid Preview extension

4. **Automatic clarification follow-ups:**
   - If your answer is too short → asks for more detail
   - If you mention a decision → asks for outcomes
   - Non-overbearing (max 1 follow-up per question)

## 🎯 Why Use This Instead of Full Flow?

| Full Flow (A→B→C) | Flow B Quickstart |
|------------------|-------------------|
| SIPOC intake questionnaire | 1 question total |
| Suppliers, Inputs, Process, Outputs, Customers | Skip to step details |
| ~15 minutes before mapping starts | Start mapping immediately |
| Good for formal assessments | **Good for getting sh*t done** |

## 📊 Viewing Your Diagram

### Option 1: VS Code (Real-time)
1. Install "Mermaid Preview" extension
2. Open `artifacts/live_bpmn_wf_1.mmd`
3. Right-click → "Open Preview to the Side"
4. Watch it update as you capture steps! ✨

### Option 2: Browser
1. Open https://mermaid.live
2. Copy contents of `artifacts/live_bpmn_wf_1.mmd`
3. Paste into editor
4. Refresh manually after each step

## 💡 Tips

- **Be specific**: "Pick items from shelf" is better than "Pick items"
- **Include roles**: The system captures who does what
- **Mention decisions**: If there's a choice/branch, say so
- **Don't overthink**: Map what actually happens today, not the ideal

## 🐛 Troubleshooting

**No diagram appearing?**
- Check debug output: `[DEBUG] Diagram written to: ...`
- Look in `artifacts/` folder
- Make sure you've committed at least one step

**Interview seems stuck?**
- Type 'quit' to exit
- Check if you're being asked a question
- Look for clarification follow-ups

**Want to start over?**
- Just run `python quickstart_flow_b.py` again
- Each session gets a fresh start

## 📁 Output Files

```
artifacts/
  └── live_bpmn_wf_1.mmd    # Your workflow diagram
```

## 🔄 Next Steps After Mapping

After you've captured your workflows:

1. **Review diagrams** - Make sure they're accurate
2. **Run Flow C (outputs)** - Generate SIPOC/swimlane diagrams and markdown summary
3. **Or export manually** - Use the Mermaid files directly

---

**Happy Mapping! 🗺️**
