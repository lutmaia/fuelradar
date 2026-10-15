"""Constantes do protocolo da modelagem v2 (docs/estudo/protocolo-modelagem.md), fixadas antes de resultados.

Mudar qualquer uma exige registrar o desvio no protocolo. As janelas vêm de `forecasting/protocol.py`.
"""

from ..forecasting.protocol import BOOTSTRAP_BLOCK_WEEKS, BOOTSTRAP_REPS, SEED  # noqa: F401

HORIZONS = (1, 2, 4)
PRIMARY_HORIZON = 2
TAU = 0.05                      # R$ por litro (R$/m³ no GNV): limiar de queda e alta
TAU_SENSITIVITY = (0.03, 0.10)
CLASSES = ("queda", "estavel", "alta")   # índices 0, 1, 2

RETRAIN_EVERY = 13              # semanas entre retreinos (janela crescente)
MIN_ORIGIN = 60                 # primeira origem de treino (índice no painel)
MIN_TRAIN_ROWS = 500

LOGIT_LAMBDA = 1.0              # penalidade L2 da logística, sobre variáveis padronizadas
LGB_CLASS_PARAMS = {
    "objective": "multiclass", "num_class": 3, "learning_rate": 0.05, "num_leaves": 31,
    "min_data_in_leaf": 40, "bagging_fraction": 0.8, "bagging_freq": 1, "feature_fraction": 0.8, "seed": 7,
    "num_threads": 1, "deterministic": True, "force_row_wise": True, "verbose": -1,
}
LGB_VALUE_PARAMS = {**{k: v for k, v in LGB_CLASS_PARAMS.items() if k not in ("objective", "num_class")},
                    "objective": "l1"}
LGB_ROUNDS = 300

EVENT_THRESHOLD = 0.02          # variação do preço de produtores que conta como reajuste
WEEKS_SINCE_CAP = 52
MOVE_THRESHOLD = 0.01           # fração de municípios que subiram/caíram: |Δ| ≥ R$ 0,01

CALIBRATION_BINS = 10
MAX_ECE = 0.05
MIN_GROUP_POINTS = 200
MIN_GROUP_BSS = -0.05
INTERVAL_QUANTILES = (0.10, 0.90)   # conformal de 80% para o valor (secundário)
DM_LAGS = 4
SIZE_LARGE, SIZE_MEDIUM, SIZE_SMALL = 20, 8, 3
SIZE_WINDOW = 26                # semanas para a mediana de postos que define o porte

PRODUCER_OF = {"GASOLINA_COMUM": "GASOLINA_A_COMUM", "GASOLINA_ADITIVADA": "GASOLINA_A_COMUM",
               "DIESEL_S10": "DIESEL_A_S10", "DIESEL_COMUM": "DIESEL_A_S500"}
LAYERS = ("L1", "L2", "L3")
MODELS = ("logistica", "lightgbm")
