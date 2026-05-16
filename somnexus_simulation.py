#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║      SomNexus × SmartVista — Executive Payment Ecosystem Simulation         ║
║      Full Python Implementation · All 5 Scenarios · Real-Time Ledger        ║
╚══════════════════════════════════════════════════════════════════════════════╝

Scenarios:
  1. Remittance → Cash Out          (80 bps earned)
  2. Remittance → WhatsApp R2P      (80 bps earned)
  3. P2P WhatsApp Transfer          (no basis points — local funds)
  4. QR Code Payment                (80 bps earned)
  5. Bajaaj Ride — Local            (no basis points — non-remittance)
"""

from __future__ import annotations

import time
import uuid
import random
from decimal import Decimal, ROUND_HALF_UP
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.rule import Rule
from rich.align import Align
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.columns import Columns
from rich import box

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────
DELAY_INSTANT = 0.25
DELAY_FAST    = 0.55
DELAY_NORMAL  = 0.90
DELAY_SLOW    = 1.30
STEP_PAUSE    = 0.70
AUTO_RUN      = True          # set False for interactive (press Enter each step)
CONSOLE_WIDTH = 100

BPS_MERCHANT   = Decimal("40")
BPS_RECIPIENT  = Decimal("20")
BPS_AGENT      = Decimal("10")
BPS_SOMNEXUS   = Decimal("10")
BPS_TOTAL      = Decimal("80")
BPS_DIVISOR    = Decimal("10000")

console = Console(width=CONSOLE_WIDTH)


# ─────────────────────────────────────────────────────────────────────────────
# DATA MODELS
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class VirtualAccount:
    """SmartVista Virtual Account (VAM)"""
    account_id:        str
    owner_name:        str
    owner_type:        str          # person | merchant | agent | driver | platform
    balance:           Decimal      = Decimal("0.00")
    currency:          str          = "USD"
    remittance_tagged: bool         = False
    kyc_status:        str          = "verified"   # verified | pending | failed
    country:           str          = "SO"

    def credit(self, amount: Decimal) -> None:
        self.balance = (self.balance + amount).quantize(Decimal("0.001"))

    def debit(self, amount: Decimal) -> None:
        if self.balance < amount:
            raise ValueError(f"Insufficient funds in {self.account_id}: "
                             f"have ${self.balance:.2f}, need ${amount:.2f}")
        self.balance = (self.balance - amount).quantize(Decimal("0.001"))

    @property
    def fmt_balance(self) -> str:
        return f"${self.balance:,.2f}"


@dataclass
class LedgerEntry:
    """SmartVista Double-Entry Ledger Row"""
    entry_id:     str      = field(default_factory=lambda: uuid.uuid4().hex[:10].upper())
    timestamp:    datetime = field(default_factory=datetime.now)
    account_id:   str      = ""
    account_name: str      = ""
    entry_type:   str      = ""    # CR | DR | BPS | INFO | CONF | FRAUD
    description:  str      = ""
    amount:       Decimal  = Decimal("0.00")
    balance_after: Decimal = Decimal("0.00")
    reference:    str      = ""


@dataclass
class BasisPointResult:
    """Result of 80-bps ecosystem distribution"""
    merchant_rebate:   Decimal
    recipient_loyalty: Decimal
    agent_incentive:   Decimal
    somnexus_margin:   Decimal
    total:             Decimal
    source_amount:     Decimal
    bps_rate:          Decimal = Decimal("80")


@dataclass
class Transaction:
    """Full Transaction Record with audit trail"""
    tx_id:          str      = field(default_factory=lambda: f"TXN-{uuid.uuid4().hex[:8].upper()}")
    timestamp:      datetime = field(default_factory=datetime.now)
    scenario:       str      = ""
    tx_type:        str      = ""   # REMITTANCE | CASHOUT | R2P | P2P | QR | QR_LOCAL
    amount:         Decimal  = Decimal("0.00")
    currency:       str      = "USD"
    sender:         str      = ""
    recipient:      str      = ""
    status:         str      = "PENDING"
    ledger_entries: List[LedgerEntry] = field(default_factory=list)
    bps_applied:    bool     = False
    bps_result:     Optional[BasisPointResult] = None
    fraud_score:    int      = 0
    settlement_ms:  int      = 0


# ─────────────────────────────────────────────────────────────────────────────
# SMARTVISTA ENGINE
# ─────────────────────────────────────────────────────────────────────────────

class SmartVistaEngine:
    """
    Core SmartVista Virtual Account Management and Ledger Engine.
    Handles: VAM creation, atomic transfers, BPS distribution,
    KYC onboarding, fraud detection.
    """

    def __init__(self):
        self.accounts:     Dict[str, VirtualAccount] = {}
        self.ledger:       List[LedgerEntry]         = []
        self.transactions: List[Transaction]          = []
        self._seq:         int                        = 0

    # ── Account management ──────────────────────────────────────────────────

    def create_account(
        self,
        account_id:    str,
        owner_name:    str,
        owner_type:    str,
        balance:       Decimal = Decimal("0"),
        remittance:    bool    = False,
        kyc_status:    str     = "verified",
    ) -> VirtualAccount:
        acc = VirtualAccount(
            account_id=account_id,
            owner_name=owner_name,
            owner_type=owner_type,
            balance=balance,
            remittance_tagged=remittance,
            kyc_status=kyc_status,
        )
        self.accounts[account_id] = acc
        return acc

    def get(self, account_id: str) -> VirtualAccount:
        if account_id not in self.accounts:
            raise KeyError(f"VAM not found: {account_id}")
        return self.accounts[account_id]

    # ── Ledger operations ───────────────────────────────────────────────────

    def _post(
        self,
        account:     VirtualAccount,
        entry_type:  str,
        description: str,
        amount:      Decimal,
        reference:   str = "",
    ) -> LedgerEntry:
        self._seq += 1
        entry = LedgerEntry(
            account_id=account.account_id,
            account_name=account.owner_name,
            entry_type=entry_type,
            description=description,
            amount=amount,
            balance_after=account.balance,
            reference=reference or f"SEQ-{self._seq:05d}",
        )
        self.ledger.append(entry)
        return entry

    def external_credit(
        self,
        account_id:      str,
        amount:          Decimal,
        description:     str  = "",
        reference:       str  = "",
        tag_remittance:  bool = False,
    ) -> LedgerEntry:
        """Credit a VAM from an external source (e.g. MTO payout)."""
        acc = self.get(account_id)
        acc.credit(amount)
        if tag_remittance:
            acc.remittance_tagged = True
        return self._post(acc, "CR", description, amount, reference)

    def transfer(
        self,
        from_id:     str,
        to_id:       str,
        amount:      Decimal,
        description: str = "",
        reference:   str = "",
    ) -> Tuple[LedgerEntry, LedgerEntry]:
        """Atomic debit-credit between two VAMs (double-entry, no partial writes)."""
        src  = self.get(from_id)
        dst  = self.get(to_id)
        ref  = reference or f"TRF-{uuid.uuid4().hex[:8].upper()}"

        src.debit(amount)
        dr = self._post(src, "DR", description or f"Transfer to {dst.owner_name}", amount, ref)

        dst.credit(amount)
        cr = self._post(dst, "CR", description or f"Transfer from {src.owner_name}", amount, ref)

        return dr, cr

    def distribute_bps(
        self,
        source_amount: Decimal,
        merchant_id:   str,
        recipient_id:  str,
        agent_id:      str,
        somnexus_id:   str,
        reference:     str = "",
    ) -> BasisPointResult:
        """Distribute 80 basis points from the remittance fee pool."""
        def calc(bps: Decimal) -> Decimal:
            return (source_amount * bps / BPS_DIVISOR).quantize(
                Decimal("0.0001"), rounding=ROUND_HALF_UP
            )

        m_amt = calc(BPS_MERCHANT)
        r_amt = calc(BPS_RECIPIENT)
        a_amt = calc(BPS_AGENT)
        s_amt = calc(BPS_SOMNEXUS)
        total = m_amt + r_amt + a_amt + s_amt

        ref = reference or f"BPS-{uuid.uuid4().hex[:8].upper()}"

        targets = [
            (merchant_id,  m_amt, f"Merchant rebate ({BPS_MERCHANT} bps)"),
            (recipient_id, r_amt, f"Recipient loyalty ({BPS_RECIPIENT} bps)"),
            (agent_id,     a_amt, f"Agent incentive ({BPS_AGENT} bps)"),
            (somnexus_id,  s_amt, f"SomNexus margin ({BPS_SOMNEXUS} bps)"),
        ]
        for acc_id, amt, desc in targets:
            acc = self.get(acc_id)
            acc.credit(amt)
            self._post(acc, "BPS", desc, amt, ref)

        return BasisPointResult(
            merchant_rebate=m_amt,
            recipient_loyalty=r_amt,
            agent_incentive=a_amt,
            somnexus_margin=s_amt,
            total=total,
            source_amount=source_amount,
        )

    def fraud_check(self, account_id: str, amount: Decimal) -> dict:
        """Simulate SmartVista fraud detection scoring."""
        acc = self.get(account_id)
        score = random.randint(2, 18)   # demo: always low risk
        checks = [
            ("velocity_check",    True),
            ("duplicate_check",   True),
            ("kyc_verification",  acc.kyc_status == "verified"),
            ("geo_validation",    True),
            ("device_fingerprint", True),
            ("merchant_risk",     True),
        ]
        return {
            "score":  score,
            "risk":   "LOW" if score < 30 else "MEDIUM" if score < 70 else "HIGH",
            "passed": score < 70,
            "checks": checks,
            "account": acc.owner_name,
        }

    def reset(self) -> None:
        self.accounts.clear()
        self.ledger.clear()
        self.transactions.clear()
        self._seq = 0


# ─────────────────────────────────────────────────────────────────────────────
# WHATSAPP GATEWAY
# ─────────────────────────────────────────────────────────────────────────────

class WhatsAppGateway:
    """Simulates the SomNexus WhatsApp integration layer."""

    @staticmethod
    def send(to: str, body: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        panel = Panel(
            Text(body, style="white"),
            title=f"[bold green]WhatsApp  →  {to}[/bold green]",
            title_align="left",
            border_style="green",
            subtitle=f"[dim green]{timestamp} EAT · Delivered ✓[/dim green]",
            subtitle_align="right",
            padding=(0, 1),
        )
        console.print(panel)
        time.sleep(DELAY_FAST)


# ─────────────────────────────────────────────────────────────────────────────
# DISPLAY HELPERS
# ─────────────────────────────────────────────────────────────────────────────

wa = WhatsAppGateway()

ENTRY_STYLES = {
    "CR":    ("[bold green]CR[/]",   "green",   "+"),
    "DR":    ("[bold red]DR[/]",     "red",     "-"),
    "BPS":   ("[bold yellow]BPS[/]", "yellow",  "+"),
    "INFO":  ("[dim cyan]INFO[/]",   "cyan",    " "),
    "CONF":  ("[bold green]✓[/]",    "green",   "✓"),
    "FRAUD": ("[bold red]FRAUD[/]",  "red",     "!"),
}


def pause(duration: float = STEP_PAUSE) -> None:
    if AUTO_RUN:
        time.sleep(duration)
    else:
        console.input("[dim]  → Press Enter to continue...[/dim]")


def spinner(label: str, duration: float) -> None:
    with Progress(
        SpinnerColumn(style="bold cyan"),
        TextColumn(f"[dim]{label}[/dim]"),
        console=console,
        transient=True,
    ) as p:
        p.add_task("", total=None)
        time.sleep(duration)


def print_step(num: int, title: str, detail: str) -> None:
    console.print(Text.assemble(
        (f"\n  ▸ Step {num}  ", "bold cyan"),
        (title,  "bold white"),
    ))
    console.print(f"    [dim]{detail}[/dim]")
    pause(DELAY_INSTANT)


def print_ok(msg: str) -> None:
    console.print(f"    [bold green]✓[/bold green]  [green]{msg}[/green]")
    pause(DELAY_INSTANT)


def print_warn(msg: str) -> None:
    console.print(f"    [bold yellow]⚠[/bold yellow]  [yellow]{msg}[/yellow]")
    pause(DELAY_INSTANT)


def print_flag(msg: str) -> None:
    console.print(f"    [bold red]✗[/bold red]  [red]{msg}[/red]")
    pause(DELAY_INSTANT)


def print_info(key: str, val: str, val_style: str = "white") -> None:
    console.print(f"    [dim]{key:<30}[/dim][{val_style}]{val}[/]")


# ── Tables ──────────────────────────────────────────────────────────────────

def show_ledger(ledger: List[LedgerEntry], title: str = "SmartVista Ledger — Live") -> None:
    t = Table(
        title=f"[bold]{title}[/bold]",
        box=box.SIMPLE_HEAVY,
        border_style="dim",
        header_style="bold dim",
        expand=True,
        show_edge=True,
    )
    t.add_column("Time",        style="dim",    width=9)
    t.add_column("Account",     style="cyan",   min_width=20)
    t.add_column("Type",        justify="center", width=7)
    t.add_column("Description", min_width=32)
    t.add_column("Amount",      justify="right", width=11)
    t.add_column("Balance",     justify="right", width=10)
    t.add_column("Reference",   style="dim",    width=14)

    for e in ledger:
        lbl, color, prefix = ENTRY_STYLES.get(e.entry_type, ("?", "white", ""))
        if e.entry_type == "DR":
            amt_str  = f"[red]-${e.amount:,.2f}[/]"
            bal_str  = f"[red]${e.balance_after:,.2f}[/]"
        elif e.entry_type in ("CR", "BPS", "CONF"):
            amt_str  = f"[green]+${e.amount:,.4f}[/]" if e.entry_type == "BPS" else f"[green]+${e.amount:,.2f}[/]"
            bal_str  = f"[green]${e.balance_after:,.2f}[/]"
        else:
            amt_str  = f"[cyan]${e.amount:,.2f}[/]"
            bal_str  = f"[white]${e.balance_after:,.2f}[/]"

        t.add_row(
            e.timestamp.strftime("%H:%M:%S"),
            e.account_name,
            lbl,
            e.description,
            amt_str,
            bal_str,
            e.reference,
        )
    console.print()
    console.print(t)


def show_balances(accounts: Dict[str, VirtualAccount],
                  highlight: Optional[List[str]] = None) -> None:
    highlight = highlight or []
    t = Table(
        title="[bold]VAM Balances — SmartVista Real-Time[/bold]",
        box=box.SIMPLE_HEAVY,
        border_style="dim",
        header_style="bold dim",
    )
    t.add_column("Account ID",  style="dim",    width=8)
    t.add_column("Owner",       min_width=22)
    t.add_column("Type",        style="dim",    width=10)
    t.add_column("Balance",     justify="right", width=12)
    t.add_column("Source",      justify="center", width=16)
    t.add_column("KYC",         justify="center", width=10)

    for aid, acc in accounts.items():
        hi   = aid in highlight
        name = f"[bold yellow]{acc.owner_name}[/]" if hi else acc.owner_name
        bal  = f"[bold green]${acc.balance:,.2f}[/]" if acc.balance > 0 else f"[dim]${acc.balance:,.2f}[/]"
        src  = "[green]Remittance ✓[/]" if acc.remittance_tagged else "[dim]Local[/]"
        kyc  = "[green]Verified ✓[/]" if acc.kyc_status == "verified" else "[yellow]Pending[/]"
        t.add_row(aid, name, acc.owner_type, bal, src, kyc)

    console.print(t)


def show_fraud(result: dict) -> None:
    color = {"LOW": "green", "MEDIUM": "yellow", "HIGH": "red"}[result["risk"]]
    console.print(Text.assemble(
        ("    🔒 Fraud engine:  ", "dim"),
        (f"Score {result['score']}/100  ", "white"),
        (f"[{result['risk']} RISK]  ", color),
        ("→ APPROVED  ", "bold green"),
    ))
    check_str = "   ".join(
        f"[{'green' if ok else 'red'}]{'✓' if ok else '✗'} {name}[/]"
        for name, ok in result["checks"]
    )
    console.print(f"    [dim]{check_str}[/dim]")
    pause(DELAY_INSTANT)


def show_bps(result: BasisPointResult) -> None:
    rows = [
        ("Merchant rebate",   result.merchant_rebate,   BPS_MERCHANT,  "yellow"),
        ("Recipient loyalty", result.recipient_loyalty,  BPS_RECIPIENT, "green"),
        ("Agent incentive",   result.agent_incentive,    BPS_AGENT,     "cyan"),
        ("SomNexus margin",   result.somnexus_margin,    BPS_SOMNEXUS,  "magenta"),
    ]
    lines = Text()
    for label, amt, bps, color in rows:
        bar_full = int(bps / BPS_MERCHANT * 24)
        bar_empty = 24 - bar_full
        lines.append(f"  {label:<22}", style="white")
        lines.append("█" * bar_full,  style=color)
        lines.append("░" * bar_empty, style="dim")
        lines.append(f"  {int(bps):>3} bps   ", style="dim")
        lines.append(f"${amt:.4f}\n", style=f"bold {color}")

    lines.append(f"\n  {'─'*22}  {'─'*24}  ─────────\n", style="dim")
    lines.append(f"  {'TOTAL':<22}", style="bold white")
    lines.append("█" * 24, style="bold yellow")
    lines.append(f"   80 bps   ", style="bold yellow")
    lines.append(f"${result.total:.4f}", style="bold yellow")
    lines.append(f"   on ${result.source_amount:.2f}\n", style="dim")

    console.print(Panel(
        lines,
        title="[bold yellow]Basis Point Distribution — Ecosystem Incentives[/bold yellow]",
        border_style="yellow",
        padding=(0, 1),
    ))


def show_no_bps(reason: str, extra: str = "") -> None:
    content = Text.assemble(
        ("  ⛔  NO BASIS POINTS\n\n", "bold red"),
        (f"  {reason}\n", "white"),
        (f"  {extra}\n" if extra else "", "dim"),
        ("\n  Source tag:      ", "dim"), ("NON-REMITTANCE\n", "bold red"),
        ("  Basis points:    ", "dim"), ("0.00 bps\n", "bold red"),
        ("  Incentive pool:  ", "dim"), ("INACTIVE — no ecosystem distribution\n", "bold red"),
    )
    console.print(Panel(content,
        title="[bold red]Basis Point Distribution[/bold red]",
        border_style="red", padding=(0, 1)))


def show_receipt(tx: Transaction) -> None:
    bps_line = (
        (f"  BPS distributed:   ", "dim"),
        (f"${tx.bps_result.total:.4f}  ({BPS_TOTAL} bps on ${tx.amount:.2f})\n", "bold yellow")
    ) if tx.bps_applied else (
        ("  BPS distributed:   ", "dim"), ("N/A — non-remittance source\n", "dim")
    )
    content = Text.assemble(
        ("  Transaction ID:    ", "dim"), (f"{tx.tx_id}\n", "bold cyan"),
        ("  Timestamp:         ", "dim"), (f"{tx.timestamp.strftime('%d %b %Y  %H:%M:%S EAT')}\n", "white"),
        ("  Type:              ", "dim"), (f"{tx.tx_type}\n", "white"),
        ("  Amount:            ", "dim"), (f"${tx.amount:,.2f} {tx.currency}\n", "bold green"),
        ("  Sender → Recipient:", "dim"), (f"{tx.sender}  →  {tx.recipient}\n", "white"),
        ("  Settlement:        ", "dim"), (f"{tx.settlement_ms}ms\n", "white"),
        ("  Fraud score:       ", "dim"), (f"{tx.fraud_score}/100  [LOW RISK]\n", "green"),
        *bps_line,
        ("  Ledger entries:    ", "dim"), (f"{len(tx.ledger_entries)}\n", "white"),
        ("  SmartVista status: ", "dim"), (f"{tx.status}  ✓\n", "bold green"),
        ("  Audit trail:       ", "dim"), ("IMMUTABLE · RECORDED\n", "green"),
    )
    console.print(Panel(content,
        title="[bold green]Transaction Receipt[/bold green]",
        border_style="green", padding=(0, 1)))
    console.print()


def scenario_banner(num: int, title: str, subtitle: str, bps_label: str) -> None:
    console.print()
    console.print(Rule(
        f"[bold yellow]  SCENARIO {num} of 5  [/bold yellow]",
        style="yellow"
    ))
    console.print(Panel(
        Align.center(Text.assemble(
            (title + "\n", "bold white"),
            (subtitle, "dim"),
        )),
        subtitle=f"[bold yellow]{bps_label}[/bold yellow]",
        subtitle_align="center",
        border_style="yellow",
        padding=(0, 4),
    ))
    console.print()


# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO 1 — REMITTANCE → CASH OUT
# ─────────────────────────────────────────────────────────────────────────────

def scenario_1(sv: SmartVistaEngine) -> None:
    scenario_banner(
        1,
        "Remittance → Cash Out",
        "Abdul (USA) sends $100 via Remitly  ·  Fatima receives in SomNexus wallet  ·  Cashes out at Al-Rashid agent",
        "80 BASIS POINTS EARNED",
    )

    sv.reset()
    fatima = sv.create_account("F001", "Fatima Hassan",     "person",   Decimal("0"))
    agent  = sv.create_account("A001", "Al-Rashid Agent",   "merchant", Decimal("500"))
    somnx  = sv.create_account("SN01", "SomNexus Platform", "platform", Decimal("10000"))
    # Agent also acts as recipient of BPS, needs its own BPS account pointer
    # For simplicity, agent and somnexus share the somnexus BPS account
    agent_bps = sv.create_account("AG01", "SomNexus Agent Pool", "agent", Decimal("200"))

    tx = Transaction(
        scenario="Remittance → Cash Out",
        tx_type="REMITTANCE+CASHOUT",
        amount=Decimal("100"),
        sender="Abdul Hassan (USA)",
        recipient="Fatima Hassan (SO)",
    )

    # ── Step 1
    print_step(1, "Abdul initiates $100 via Remitly", "Minneapolis, USA  →  Mogadishu, Somalia")
    print_info("Sender:", "Abdul Hassan")
    print_info("MTO:", "Remitly (prefunded liquidity)")
    print_info("Amount:", "$100.00 USD")
    print_info("Destination:", "Mogadishu, Somalia")
    spinner("Remitly processing outbound transfer...", DELAY_NORMAL)
    print_ok("Remitly transfer accepted — payout instruction queued")
    pause(DELAY_FAST)

    # ── Step 2
    print_step(2, "Remitly API → SomNexus payout request", "REST API call  ·  Beneficiary details  ·  FX params")
    spinner("SomNexus API validating payout instruction...", DELAY_FAST)
    print_ok("Payout instruction authenticated and validated")
    print_info("API endpoint:", "/v2/payouts/initiate")
    print_info("Beneficiary:", "Fatima Hassan (+252 61 XXX XXXX)")
    print_info("Reference:", "REM-2026-0001")
    pause(DELAY_FAST)

    # ── Step 3
    print_step(3, "SmartVista credits Fatima's Virtual Account", "New recipient → KYC onboarding triggered via WhatsApp")
    spinner("Running NIRA ID verification (Option 1)...", DELAY_SLOW)
    print_ok("NIRA ID verified — KYC COMPLETE")
    print_ok("Fatima VAM created: F001")
    e = sv.external_credit("F001", Decimal("100"),
                           "Inbound remittance — Abdul via Remitly",
                           "REM-2026-0001", tag_remittance=True)
    tx.ledger_entries.append(e)
    print_info("VAM F001 balance:", "$100.00")
    print_info("Remittance tag:", "REMITTANCE_ORIGINATED = TRUE")
    pause(DELAY_FAST)

    # ── Step 4
    print_step(4, "WhatsApp instant notification to Fatima", "Zero app download · instant delivery")
    wa.send("Fatima Hassan",
        "✅ You received $100.00 from Abdul (USA via Remitly)\n\n"
        "💰 Your balance: $100.00\n\n"
        "What would you like to do?\n"
        "  [💸 Cash Out]   [🛒 Pay Merchant]   [📊 Balance]"
    )

    # ── Step 5
    print_step(5, "Fatima selects Cash Out → scans Al-Rashid QR", "SomNexus initiates cash-out flow through SmartVista")
    fraud = sv.fraud_check("F001", Decimal("100"))
    tx.fraud_score = fraud["score"]
    show_fraud(fraud)
    wa.send("Fatima → Al-Rashid Agent",
        "🔄 Cash-out request\n\n"
        "💵 Amount:  $100.00\n"
        "🏪 Agent:   Al-Rashid Money Exchange\n"
        "📍 Location: Hodan District, Mogadishu\n\n"
        "⏳ Processing via SmartVista..."
    )

    # ── Step 6
    print_step(6, "SmartVista atomic ledger transfer", "Debit Fatima VAM  ·  Credit Merchant VAM  ·  Single atomic write")
    start = time.perf_counter()
    spinner("SmartVista executing atomic debit-credit...", DELAY_NORMAL)
    dr, cr = sv.transfer("F001", "A001", Decimal("100"),
                         "Cash-out payment", "CSH-2026-0001")
    elapsed = int((time.perf_counter() - start) * 1000)
    tx.ledger_entries.extend([dr, cr])
    tx.settlement_ms = elapsed
    print_ok(f"Ledger committed in {elapsed}ms — zero settlement risk")
    print_info("Fatima VAM balance:", "$0.00")
    print_info("Al-Rashid balance:", "$600.00")
    pause(DELAY_FAST)

    # ── Step 7
    print_step(7, "Merchant delivers cash + SomNexus sends confirmation code", "6-digit code — share ONLY after receiving physical cash")
    conf_code = f"{random.randint(100, 999)}-{random.randint(100, 999)}"
    wa.send("SomNexus Wallet  🔐",
        f"Cash-out confirmation code\n\n"
        f"  ████  {conf_code}  ████\n\n"
        f"Share this code with the agent ONLY after you\n"
        f"have received your $100 in cash.\n"
        f"Code expires in 10 minutes."
    )
    print_ok(f"Confirmation code delivered: {conf_code}")
    pause(DELAY_FAST)

    # ── Step 8 — BPS
    print_step(8, "Basis points distributed across ecosystem", "80 bps from Remitly remittance fee pool  ·  4 participants rewarded")
    spinner("SmartVista calculating and distributing basis points...", DELAY_NORMAL)
    bps = sv.distribute_bps(
        Decimal("100"), "A001", "F001", "AG01", "SN01", "BPS-2026-0001"
    )
    tx.bps_applied = True
    tx.bps_result  = bps
    tx.status      = "COMPLETED"

    show_bps(bps)
    show_ledger(sv.ledger, "Scenario 1 — Complete Ledger")
    show_balances(sv.accounts, ["F001", "A001"])
    show_receipt(tx)

    pause(DELAY_SLOW)
    console.input("  [dim]Press Enter for Scenario 2  →  WhatsApp R2P...[/dim]\n")


# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO 2 — REMITTANCE → WHATSAPP R2P
# ─────────────────────────────────────────────────────────────────────────────

def scenario_2(sv: SmartVistaEngine) -> None:
    scenario_banner(
        2,
        "WhatsApp Request-to-Pay (R2P)",
        "Al-Noor Grocery sends R2P to Fatima  ·  One-tap approval  ·  Remittance-funded → 80 bps activated",
        "80 BASIS POINTS EARNED",
    )

    sv.reset()
    fatima   = sv.create_account("F001", "Fatima Hassan",    "person",   Decimal("100"), remittance=True)
    merchant = sv.create_account("M001", "Al-Noor Grocery",  "merchant", Decimal("200"))
    agent    = sv.create_account("AG01", "SomNexus Agent",   "agent",    Decimal("100"))
    somnx    = sv.create_account("SN01", "SomNexus Platform","platform", Decimal("10000"))

    tx = Transaction(
        scenario="WhatsApp R2P",
        tx_type="R2P",
        amount=Decimal("85"),
        sender="Fatima Hassan (payer)",
        recipient="Al-Noor Grocery (merchant)",
    )

    # ── Step 1
    print_step(1, "Fatima holds $100 remittance-tagged balance", "SmartVista tag: REMITTANCE_ORIGINATED = TRUE  →  80 bps eligible")
    print_info("Fatima VAM F001 balance:", "$100.00")
    print_info("Remittance tag:", "✓ REMITTANCE_ORIGINATED = TRUE")
    print_info("BPS eligibility:", "✓ 80 bps pool ACTIVE for all spends")
    pause(DELAY_FAST)

    # ── Step 2
    print_step(2, "Al-Noor Grocery sends R2P via WhatsApp", "Merchant interface → SomNexus → WhatsApp Gateway → Fatima  (right-to-left flow)")
    spinner("SomNexus routing R2P request to Fatima...", DELAY_FAST)
    wa.send("Al-Noor Grocery → Fatima Hassan",
        "💳 PAYMENT REQUEST\n\n"
        "🏪 Al-Noor Grocery — Mogadishu\n"
        "Amount:  $85.00\n"
        "Items:   Groceries\n"
        "Ref:     INV-2024-0847\n\n"
        "  [✅ Approve payment]   [❌ Decline]"
    )

    # ── Step 3
    print_step(3, "Fatima approves with one tap", "Biometric auto-auth — no PIN — < 1 second authorization")
    spinner("Biometric authentication...", DELAY_FAST)
    fraud = sv.fraud_check("F001", Decimal("85"))
    tx.fraud_score = fraud["score"]
    show_fraud(fraud)
    print_ok("Payment authorized — biometric confirmed")
    wa.send("Fatima Hassan → SomNexus",
        "✅ Payment approved\n\n"
        "💵 $85.00 → Al-Noor Grocery\n"
        "🔐 Auth: Biometric ✓\n"
        "⚡ Routing via SmartVista..."
    )

    # ── Step 4
    print_step(4, "SmartVista real-time settlement", "Atomic debit F001 · credit M001 · zero clearing delay · final and immediate")
    start = time.perf_counter()
    spinner("SmartVista settling R2P...", DELAY_NORMAL)
    dr, cr = sv.transfer("F001", "M001", Decimal("85"), "R2P payment — Al-Noor Grocery", "R2P-2026-0001")
    elapsed = int((time.perf_counter() - start) * 1000)
    tx.ledger_entries.extend([dr, cr])
    tx.settlement_ms = elapsed
    print_ok(f"Settled in {elapsed}ms — both VAMs updated")
    print_info("Fatima balance:", "$15.00")
    print_info("Al-Noor balance:", "$285.00")
    pause(DELAY_FAST)

    # ── Step 5
    print_step(5, "Instant WhatsApp receipts — both parties", "Fatima + merchant portal update in real-time")
    wa.send("SomNexus Wallet ✅",
        "Payment confirmed!\n\n"
        "💸 $85.00 → Al-Noor Grocery\n"
        "💰 Your balance: $15.00\n"
        "🕐 15 May 2026, 14:32:07 EAT\n"
        "Ref: R2P-2026-0001"
    )

    # ── Step 6 — BPS
    print_step(6, "Basis points rewarded — remittance-funded spend", "SmartVista: REMITTANCE_ORIGINATED = TRUE → 80 bps pool activates on $85 purchase")
    spinner("SmartVista distributing ecosystem incentives...", DELAY_NORMAL)
    bps = sv.distribute_bps(
        Decimal("85"), "M001", "F001", "AG01", "SN01", "BPS-2026-0002"
    )
    tx.bps_applied = True
    tx.bps_result  = bps
    tx.status      = "COMPLETED"

    show_bps(bps)
    show_ledger(sv.ledger, "Scenario 2 — Complete Ledger")
    show_balances(sv.accounts, ["F001", "M001"])
    show_receipt(tx)

    pause(DELAY_SLOW)
    console.input("  [dim]Press Enter for Scenario 3  →  P2P Transfer...[/dim]\n")


# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO 3 — P2P WHATSAPP TRANSFER (NO BPS)
# ─────────────────────────────────────────────────────────────────────────────

def scenario_3(sv: SmartVistaEngine) -> None:
    scenario_banner(
        3,
        "P2P WhatsApp → WhatsApp Transfer",
        "Ali sends $50 to Fatima  ·  Both on SomNexus  ·  Local salary funds  ·  NON-REMITTANCE",
        "NO BASIS POINTS — LOCAL TRANSACTION",
    )

    sv.reset()
    ali    = sv.create_account("AL01", "Ali Omar",      "person", Decimal("200"), remittance=False)
    fatima = sv.create_account("F001", "Fatima Hassan", "person", Decimal("15"),  remittance=False)

    tx = Transaction(
        scenario="P2P WhatsApp Transfer",
        tx_type="P2P",
        amount=Decimal("50"),
        sender="Ali Omar",
        recipient="Fatima Hassan",
    )

    # ── Step 1
    print_step(1, "Ali opens WhatsApp payment", "Selects 'Send Money' · searches Fatima by phone number · enters $50")
    wa.send("Ali's SomNexus Wallet",
        "💸 Send money\n\n"
        "To:      Fatima Hassan (+252 61 *** ****)\n"
        "Amount:  $50.00\n"
        "Balance: $200.00\n\n"
        "  [🔐 Confirm with PIN]"
    )

    # ── Step 2
    print_step(2, "Ali authenticates with 4-digit PIN", "SomNexus validates VAM balance  ·  Routes to SmartVista")
    spinner("Validating PIN...", DELAY_FAST)
    fraud = sv.fraud_check("AL01", Decimal("50"))
    tx.fraud_score = fraud["score"]
    show_fraud(fraud)
    print_ok("PIN verified — balance sufficient — transfer queued")
    pause(DELAY_FAST)

    # ── Step 3
    print_step(3, "SmartVista atomic P2P transfer", "Single atomic ledger write — no float, no hold, no intermediary")
    start = time.perf_counter()
    spinner("SmartVista executing P2P transfer...", DELAY_NORMAL)
    dr, cr = sv.transfer("AL01", "F001", Decimal("50"), "P2P transfer", "P2P-2026-0001")
    elapsed = int((time.perf_counter() - start) * 1000)
    tx.ledger_entries.extend([dr, cr])
    tx.settlement_ms = elapsed
    print_ok(f"Transfer complete in {elapsed}ms — instant, no intermediary")
    print_info("Ali balance:", "$150.00")
    print_info("Fatima balance:", "$65.00")
    pause(DELAY_FAST)

    # ── Step 4
    print_step(4, "Ali receives send confirmation", "Instant receipt — updated balance")
    wa.send("SomNexus Wallet → Ali",
        "Sent!\n\n"
        "💸 $50.00  →  Fatima Hassan\n"
        "💰 Your balance: $150.00\n"
        "🕐 15 May 2026, 09:14:33 EAT\n"
        "Ref: P2P-2026-0001"
    )

    # ── Step 5
    print_step(5, "Fatima receives funds", "Instant WhatsApp notification — real-time balance update")
    wa.send("SomNexus Wallet → Fatima",
        "Received!\n\n"
        "✅ $50.00 from Ali Omar\n"
        "💰 Your balance: $65.00\n"
        "🕐 15 May 2026, 09:14:33 EAT\n"
        "Ref: P2P-2026-0001"
    )

    # ── Step 6 — Source check
    print_step(6, "SmartVista source check — NON-REMITTANCE detected", "Ali.remittance_tagged = False  →  80 bps pool = INACTIVE")
    console.print()
    console.print(Text.assemble(
        ("    SmartVista source engine:\n\n", "dim"),
        ("      ali.remittance_tagged   = ", "dim"), ("False\n", "bold red"),
        ("      fatima.remittance_tagged = ", "dim"), ("False\n", "bold red"),
        ("\n    Result:\n\n", "dim"),
        ("      Basis point pool:        ", "dim"), ("INACTIVE\n", "bold red"),
        ("      Ecosystem incentives:    ", "dim"), ("NOT DISTRIBUTED\n", "bold red"),
        ("      80 bps:                  ", "dim"), ("$0.0000 to 0 participants\n", "bold red"),
        ("\n    Why this matters:\n\n", "dim"),
        ("      Only international remittance inflows earn ecosystem incentives.\n", "white"),
        ("      This protects the integrity of the remittance incentive model.\n", "white"),
    ))
    pause(DELAY_FAST)

    tx.status = "COMPLETED"
    show_no_bps(
        "Ali's funds originate from a local salary deposit — not a remittance inflow.",
        "Remittance incentives exist to encourage international capital to flow digitally into Somalia."
    )
    show_ledger(sv.ledger, "Scenario 3 — Complete Ledger")
    show_balances(sv.accounts, ["AL01", "F001"])
    show_receipt(tx)

    pause(DELAY_SLOW)
    console.input("  [dim]Press Enter for Scenario 4  →  QR Code Payment...[/dim]\n")


# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO 4 — QR CODE PAYMENT
# ─────────────────────────────────────────────────────────────────────────────

def scenario_4(sv: SmartVistaEngine) -> None:
    scenario_banner(
        4,
        "QR Code Payment",
        "Fatima scans Hormuud Supermarket QR via WhatsApp  ·  < 500ms settlement  ·  80 bps earned",
        "80 BASIS POINTS EARNED",
    )

    sv.reset()
    fatima = sv.create_account("F001", "Fatima Hassan",        "person",   Decimal("100"), remittance=True)
    market = sv.create_account("MK01", "Hormuud Supermarket",  "merchant", Decimal("350"))
    agent  = sv.create_account("AG01", "SomNexus Agent",       "agent",    Decimal("100"))
    somnx  = sv.create_account("SN01", "SomNexus Platform",    "platform", Decimal("10000"))

    tx = Transaction(
        scenario="QR Code Payment",
        tx_type="QR",
        amount=Decimal("45"),
        sender="Fatima Hassan",
        recipient="Hormuud Supermarket",
    )

    # ── Step 1
    print_step(1, "Fatima opens WhatsApp QR scanner", "Tap QR icon in SomNexus menu  ·  Camera opens instantly  ·  No app-switching")
    print_info("Fatima VAM F001 balance:", "$100.00")
    print_info("Remittance tag:", "✓ REMITTANCE_ORIGINATED = TRUE")
    pause(DELAY_FAST)

    # ── Step 2
    print_step(2, "Scans Hormuud Supermarket QR code", "< 2 seconds  ·  Merchant name, location, ID displayed in WhatsApp")
    spinner("Decoding QR payload (MRC-4829)...", DELAY_FAST)
    print_ok("QR decoded — Merchant: Hormuud Supermarket · Verified ✓")
    wa.send("SomNexus Scanner",
        "QR detected ✅\n\n"
        "🏬 Hormuud Supermarket\n"
        "    Mogadishu, Hodan District\n"
        "    Merchant ID: MRC-4829\n"
        "    Verified merchant ✓\n\n"
        "  [$10]   [$25]   [$45]   [Custom amount]"
    )

    # ── Step 3
    print_step(3, "Fatima confirms $45 payment", "Auto-approved for amounts < $100  ·  Zero PIN friction  ·  One tap")
    spinner("Auto-approval engine...", DELAY_FAST)
    fraud = sv.fraud_check("F001", Decimal("45"))
    tx.fraud_score = fraud["score"]
    show_fraud(fraud)
    print_ok("Auto-approved — no PIN required for sub-$100 transaction")
    wa.send("SomNexus Wallet",
        "Confirm payment?\n\n"
        "🏬 Hormuud Supermarket\n"
        "💵 Amount:  $45.00\n"
        "💰 After:   $55.00 remaining\n\n"
        "  [✅ Pay now]   [❌ Cancel]"
    )

    # ── Step 4
    print_step(4, "SmartVista instant settlement (< 500ms)", "Both VAMs update simultaneously · Merchant POS turns green instantly")
    start = time.perf_counter()
    spinner("SmartVista processing QR payment...", 0.45)
    dr, cr = sv.transfer("F001", "MK01", Decimal("45"),
                         "QR payment — Hormuud Supermarket", "QR-2026-0001")
    elapsed = int((time.perf_counter() - start) * 1000)
    tx.ledger_entries.extend([dr, cr])
    tx.settlement_ms = elapsed
    print_ok(f"Settled in {elapsed}ms — Merchant POS: GREEN ✓")
    print_info("Fatima balance:", "$55.00")
    print_info("Hormuud balance:", "$395.00")
    pause(DELAY_FAST)

    # ── Step 5
    print_step(5, "Receipts delivered instantly — both parties", "WhatsApp + merchant portal + POS updated in real-time")
    wa.send("SomNexus Wallet ✅",
        "Payment confirmed!\n\n"
        "✅ $45.00  →  Hormuud Supermarket\n"
        "💰 Your balance: $55.00\n"
        "🕐 15 May 2026, 11:47:22 EAT\n"
        "Ref: QR-2026-0001"
    )

    # ── Step 6 — BPS
    print_step(6, "Basis points rewarded — remittance-funded QR purchase", "Remittance tag on Fatima's balance → 80 bps activates on $45 QR payment")
    spinner("Distributing ecosystem incentives...", DELAY_NORMAL)
    bps = sv.distribute_bps(
        Decimal("45"), "MK01", "F001", "AG01", "SN01", "BPS-2026-0003"
    )
    tx.bps_applied = True
    tx.bps_result  = bps
    tx.status      = "COMPLETED"

    show_bps(bps)
    show_ledger(sv.ledger, "Scenario 4 — Complete Ledger")
    show_balances(sv.accounts, ["F001", "MK01"])
    show_receipt(tx)

    pause(DELAY_SLOW)
    console.input("  [dim]Press Enter for Scenario 5  →  Bajaaj Ride (Local)...[/dim]\n")


# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO 5 — BAJAAJ RIDE (LOCAL, NON-REMITTANCE)
# ─────────────────────────────────────────────────────────────────────────────

def scenario_5(sv: SmartVistaEngine) -> None:
    scenario_banner(
        5,
        "Bajaaj Ride — Local Transaction",
        "Ahmed pays $2 Bajaaj fare  ·  Local salary funds  ·  NON-REMITTANCE  ·  Zero basis points",
        "NO BASIS POINTS — NON-REMITTANCE SOURCE",
    )

    sv.reset()
    ahmed  = sv.create_account("AH01", "Ahmed Mohamed",    "person", Decimal("25"), remittance=False)
    hassan = sv.create_account("DR01", "Hassan (Bajaaj)",  "driver", Decimal("8"),  remittance=False)

    tx = Transaction(
        scenario="Bajaaj Ride — Local",
        tx_type="QR_LOCAL",
        amount=Decimal("2"),
        sender="Ahmed Mohamed",
        recipient="Hassan (Bajaaj Driver)",
    )

    # ── Step 1
    print_step(1, "Ahmed boards Hassan's Bajaaj in Mogadishu", "Hassan has a printed SomNexus QR laminated to dashboard — cost = $0")
    print_info("Ahmed VAM AH01 balance:", "$25.00")
    print_info("Remittance tag:", "✗ LOCAL (salary deposit)")
    print_info("Hassan QR:", "DRV-7734 · Printed once · Never changes")
    pause(DELAY_FAST)

    # ── Step 2
    print_step(2, "Hassan displays printed QR code", "Links to Hassan's VAM  ·  Any WhatsApp user can pay  ·  No bank account needed")
    print_info("QR payload:", "DRV-7734 · Hassan Mohamed · Bajaaj driver")
    print_info("Acceptance method:", "Printed QR — zero-cost, offline-compatible")
    pause(DELAY_FAST)

    # ── Step 3
    print_step(3, "Ahmed scans QR via WhatsApp camera", "< 2 seconds  ·  Driver name and $2 fare appear immediately")
    spinner("Decoding QR (DRV-7734)...", DELAY_FAST)
    print_ok("QR decoded — Hassan's Bajaaj taxi · Verified ✓")
    wa.send("SomNexus Scanner",
        "QR detected ✅\n\n"
        "🛺 Hassan's Bajaaj taxi\n"
        "    Driver ID: DRV-7734\n"
        "    Verified driver ✓\n"
        "    Fare: $2.00\n\n"
        "  [✅ Pay $2.00]   [❌ Cancel]"
    )

    # ── Step 4
    print_step(4, "SmartVista transfers $2 in < 300ms", "Ahmed VAM → Hassan VAM  ·  No cash exchanged  ·  No change needed")
    start = time.perf_counter()
    spinner("SmartVista processing Bajaaj fare...", 0.28)
    dr, cr = sv.transfer("AH01", "DR01", Decimal("2"), "Bajaaj fare", "BJ-2026-0001")
    elapsed = int((time.perf_counter() - start) * 1000)
    tx.ledger_entries.extend([dr, cr])
    tx.settlement_ms = elapsed
    tx.fraud_score = sv.fraud_check("AH01", Decimal("2"))["score"]
    print_ok(f"Fare paid in {elapsed}ms — no cash, no change, no friction")
    print_info("Ahmed balance:", "$23.00")
    print_info("Hassan balance:", "$10.00")
    pause(DELAY_FAST)

    # ── Step 5
    print_step(5, "Instant confirmations + SmartVista loyalty promo recorded", "Hassan 5% off next ride · SmartVista loyalty module activated")
    wa.send("SomNexus Wallet → Ahmed",
        "Paid!\n\n"
        "🛺 $2.00  →  Hassan (Bajaaj)\n"
        "💰 Your balance: $23.00\n"
        "🕐 15 May 2026, 08:22:11 EAT\n\n"
        "🎁 Hassan's promo: 5% off your next ride\n"
        "   (SmartVista Loyalty Module)"
    )
    wa.send("SomNexus Wallet → Hassan",
        "Fare received!\n\n"
        "✅ $2.00 from Ahmed Mohamed\n"
        "💰 Your balance: $10.00\n"
        "🕐 15 May 2026, 08:22:11 EAT"
    )

    # ── Step 6 — Source check
    print_step(6, "SmartVista source check — NON-REMITTANCE — pool INACTIVE", "Local salary deposit tag → 80 bps pool does NOT activate")
    console.print()
    console.print(Text.assemble(
        ("    SmartVista source engine output:\n\n", "dim"),
        ("      ahmed.remittance_tagged    = ", "dim"), ("False\n", "bold red"),
        ("      Transaction type:          ", "dim"), ("QR_LOCAL\n", "yellow"),
        ("      Remittance origin check:   ", "dim"), ("FAILED — local source\n", "bold red"),
        ("\n    Decision:\n\n", "dim"),
        ("      80 bps incentive pool:     ", "dim"), ("INACTIVE\n", "bold red"),
        ("      Ecosystem distribution:    ", "dim"), ("$0.0000 to 0 participants\n", "bold red"),
        ("      Loyalty module:            ", "dim"), ("Hassan 5% promo RECORDED\n", "bold yellow"),
        ("\n    Explanation for executives:\n\n", "dim"),
        ("      The 80 bps incentive model exists to pull international remittance\n", "white"),
        ("      dollars into the digital economy. Local transactions like taxi rides,\n", "white"),
        ("      grocery purchases, and local P2P transfers do not receive remittance\n", "white"),
        ("      basis points — this preserves the model's integrity and commercial\n", "white"),
        ("      sustainability. Merchants may still offer promotional discounts\n", "white"),
        ("      through the SmartVista loyalty module.\n", "white"),
    ))
    pause(DELAY_FAST)

    tx.status = "COMPLETED"
    show_no_bps(
        "Ahmed's funds are from a local salary deposit — not an international remittance.",
        "SmartVista loyalty module records Hassan's 5% promo for the next ride."
    )
    show_ledger(sv.ledger, "Scenario 5 — Complete Ledger")
    show_balances(sv.accounts, ["AH01", "DR01"])
    show_receipt(tx)


# ─────────────────────────────────────────────────────────────────────────────
# EXECUTIVE SUMMARY
# ─────────────────────────────────────────────────────────────────────────────

def executive_summary() -> None:
    console.print()
    console.print(Rule("[bold yellow]  EXECUTIVE SUMMARY — ALL SCENARIOS  [/bold yellow]", style="yellow"))
    console.print()

    # Comparison table
    t = Table(
        title="[bold]SomNexus × SmartVista — Complete Scenario Comparison[/bold]",
        box=box.SIMPLE_HEAVY,
        border_style="yellow",
        header_style="bold yellow",
        expand=True,
    )
    t.add_column("Scenario",           min_width=26)
    t.add_column("Method",             width=12)
    t.add_column("Amount",             justify="right", width=8)
    t.add_column("Settlement",         justify="center", width=12)
    t.add_column("Remittance",         justify="center", width=13)
    t.add_column("Basis Points",       justify="right", width=12)
    t.add_column("Ecosystem $",        justify="right", width=11)

    data = [
        ("Remittance → Cash Out",    "Cash Out",   "$100.00", "< 1,000ms",  True,  "80 bps", "$0.8000"),
        ("Remittance → R2P",         "WhatsApp",   "$85.00",  "< 1,000ms",  True,  "80 bps", "$0.6800"),
        ("P2P WhatsApp Transfer",    "P2P",         "$50.00",  "< 1,000ms",  False, "0 bps",  "$0.0000"),
        ("QR Code Payment",          "QR Scan",    "$45.00",  "< 500ms",    True,  "80 bps", "$0.3600"),
        ("Bajaaj Ride — Local",      "QR Scan",    "$2.00",   "< 300ms",    False, "0 bps",  "$0.0000"),
    ]

    for name, method, amt, settle, is_rem, bps, bps_val in data:
        t.add_row(
            name,
            method,
            f"[bold]{amt}[/]",
            f"[green]{settle}[/]",
            "[green]✓ Remittance[/]" if is_rem else "[red]✗ Local[/]",
            f"[bold yellow]{bps}[/]" if is_rem else f"[dim]{bps}[/]",
            f"[bold yellow]{bps_val}[/]" if is_rem else f"[dim]{bps_val}[/]",
        )
    console.print(t)

    # BPS mechanics panel
    console.print(Panel(
        Text.assemble(
            ("  Basis Point Engine — How 80 bps Works on $100 Spend:\n\n", "bold white"),
            ("    Merchant rebate   (40 bps)  ", "yellow"),
            ("→ $0.0040 per dollar  ·  Incentivises merchants to accept digital\n", "dim"),
            ("    Recipient loyalty (20 bps)  ", "green"),
            ("→ $0.0020 per dollar  ·  Rewards recipients who spend digitally\n", "dim"),
            ("    Agent incentive   (10 bps)  ", "cyan"),
            ("→ $0.0010 per dollar  ·  Rewards agents who grow the network\n", "dim"),
            ("    SomNexus margin   (10 bps)  ", "magenta"),
            ("→ $0.0010 per dollar  ·  Platform sustainability\n", "dim"),
            ("    ─────────────────────────────────────────────────────────\n", "dim"),
            ("    Total             (80 bps)  ", "bold yellow"),
            ("→ $0.0080 per dollar  ·  Funded from MTO remittance fee pool\n", "bold yellow"),
        ),
        title="[bold yellow]Basis Point Mechanics[/bold yellow]",
        border_style="yellow",
        padding=(0, 1),
    ))

    # Key insights
    console.print(Panel(
        Text.assemble(
            ("  KEY INSIGHTS FOR EXECUTIVE DECISION-MAKING\n\n", "bold white"),
            ("  ●  ", "yellow"), ("All 5 payment methods settle in < 1 second via SmartVista VAM — no clearing delay\n", "white"),
            ("  ●  ", "yellow"), ("80 basis points activate ONLY on remittance-funded spending — protects incentive integrity\n", "white"),
            ("  ●  ", "yellow"), ("Every ecosystem participant earns: merchant 40 bps · recipient 20 bps · agent 10 bps · SomNexus 10 bps\n", "white"),
            ("  ●  ", "yellow"), ("WhatsApp = zero app download · QR = zero-cost merchant acceptance (print once, use forever)\n", "white"),
            ("  ●  ", "yellow"), ("P2P local transfers and local QR payments earn ZERO bps — clear and enforceable model boundary\n", "white"),
            ("  ●  ", "yellow"), ("SmartVista provides: full audit trail · fraud detection · dual-entry ledger · KYC for every transaction\n", "white"),
            ("  ●  ", "yellow"), ("NFC tap payments (not shown) use identical basis point model — same 80 bps distribution\n", "white"),
            ("  ●  ", "yellow"), ("Bajaaj/local merchants can still receive SmartVista loyalty module promotional discounts\n", "white"),
        ),
        title="[bold white]Key Insights[/bold white]",
        border_style="white",
        padding=(0, 1),
    ))

    console.print(Panel(
        Align.center(Text.assemble(
            ("Simulation complete.\n", "bold green"),
            ("All 5 SomNexus × SmartVista payment scenarios demonstrated.\n", "dim"),
            ("Full ledger, fraud detection, KYC, BPS engine, WhatsApp gateway — all systems live.\n", "dim"),
        )),
        border_style="green",
        padding=(0, 2),
    ))
    console.print()


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def print_header() -> None:
    console.print()
    console.print(Panel(
        Align.center(Text.assemble(
            ("SomNexus  ×  SmartVista\n", "bold yellow"),
            ("Payment Ecosystem — Executive Simulation\n\n", "bold white"),
            ("Python 3.12  ·  5 Scenarios  ·  Real-Time Ledger Engine  ·  Full BPS Distribution\n", "dim"),
            ("Remittance · Cash-Out · R2P · P2P · QR · Bajaaj · Fraud Detection · KYC · WhatsApp\n", "dim"),
        )),
        border_style="yellow",
        padding=(1, 6),
    ))

    t = Table(box=box.SIMPLE, border_style="dim", show_header=False, expand=True)
    t.add_column("", style="dim", width=22)
    t.add_column("", style="white")
    t.add_column("", style="dim", width=22)
    t.add_column("", style="white")
    t.add_row("Engine",         "SmartVista VAM",       "BPS Model",  "80 bps (4 participants)")
    t.add_row("Gateway",        "WhatsApp + QR + NFC",  "Settlement", "< 1,000ms atomic")
    t.add_row("Fraud engine",   "Real-time scoring",    "Ledger",     "Double-entry, immutable")
    t.add_row("KYC",            "NIRA ID / Biometric",  "Currency",   "USD")
    console.print(t)
    console.print()


def main() -> None:
    sv = SmartVistaEngine()

    print_header()
    console.input("  [dim]Press Enter to begin Scenario 1  →  Remittance + Cash Out...[/dim]\n")

    scenario_1(sv)
    scenario_2(sv)
    scenario_3(sv)
    scenario_4(sv)
    scenario_5(sv)

    executive_summary()


if __name__ == "__main__":
    main()
