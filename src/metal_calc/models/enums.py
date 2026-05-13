from __future__ import annotations
from enum import Enum, auto


class PriceProfile(int, Enum):
    MARGIN_0 = 0
    MARGIN_20 = 20
    MARGIN_45 = 45

    def label(self) -> str:
        return f"Marża {self.value}%"


class ProductFamily(str, Enum):
    WIRE = "drut"
    SHEET = "blacha"
    TUBE = "rura_profil"
    MESH = "siatka"
    STRUCTURE = "konstrukcja"

    def label_pl(self) -> str:
        return {
            self.WIRE: "Drut",
            self.SHEET: "Blacha",
            self.TUBE: "Rura / Profil",
            self.MESH: "Siatka / Rama",
            self.STRUCTURE: "Konstrukcja / Regał",
        }[self]


class OperationType(str, Enum):
    # Wire
    STRAIGHTENING = "prostowanie_ciecie"
    WIRE_BENDING = "giecie_drutu"
    WELDING_SPOT = "zgrzewanie"

    # Sheet
    NESTING = "nesting"
    LASER_CUTTING = "ciecie_laserem"
    PUNCHING = "wykrawanie"
    DEBURRING = "gratowanie"
    SHEET_BENDING = "giecie_blachy"

    # Tube / profile
    TUBE_CUTTING = "ciecie_rury"
    TUBE_BENDING = "giecie_rury"
    DRILLING = "wiercenie_fazowanie"

    # Welding (shared)
    WELDING_ROBOT = "spawanie_robot"
    WELDING_MANUAL = "spawanie_reczne"

    # Finish
    POWDER_COATING = "malowanie_proszkowe"
    FLUID_COATING = "malowanie_fluidyzacyjne"
    GALVANIZING = "cynkowanie"          # outside service
    CHROMATING = "chromowanie"          # outside service
    SANDBLASTING = "piaskowanie"        # outside service

    # Assembly / packaging
    ASSEMBLY = "montaz"
    PACKAGING = "pakowanie"
    PACKAGING_AUTO = "pakowanie_auto"


class MaterialFamily(str, Enum):
    STEEL_BLACK = "stal_czarna"
    STEEL_STAINLESS = "stal_nierdzewna"
    STEEL_GALVANIZED = "stal_ocynkowana"
    ALUMINUM = "aluminium"
    COPPER = "miedz"
    OTHER = "inny"


class MaterialForm(str, Enum):
    WIRE = "drut"
    SHEET = "blacha"
    TUBE_ROUND = "rura_okragla"
    TUBE_SQUARE = "rura_kwadratowa"
    PROFILE = "profil"
    FLAT_BAR = "plaskownik"
    ROD = "pretlrundowy"


class PriceSource(str, Enum):
    MONTHLY_LIST = "cennik_miesięczny"
    ERP_LAST_MOVEMENT = "erp_ostatni_ruch"
    PROCUREMENT_QUERY = "zapytanie_zaopatrzenie"
    TEMPORARY_RULE = "regula_tymczasowa"


class OutsideServiceType(str, Enum):
    GALVANIZING_DRUM = "cynkowanie_bebn"
    GALVANIZING_TRAVERSE = "cynkowanie_trawers"
    CHROMATING = "chromowanie"
    SANDBLASTING = "piaskowanie"
    OTHER = "inne"


class RFQStatus(str, Enum):
    NEW = "nowe"
    MISSING_DATA = "braki_danych"
    READY_FOR_CALC = "gotowe_do_kalkulacji"
    IN_PROGRESS = "w_trakcie"
    QUOTED = "wycenione"
    SENT = "wyslane"
    CANCELLED = "anulowane"


class QuoteStatus(str, Enum):
    DRAFT = "szkic"
    REVIEW = "do_weryfikacji"
    APPROVED = "zatwierdzona"
    SENT = "wyslana"
    ACCEPTED = "przyjeta"
    REJECTED = "odrzucona"
    EXPIRED = "przeterminowana"
