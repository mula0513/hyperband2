import numpy as np
from optimizers.tpe.hyperopt_august2013_mod_src.hyperopt import hp


space = {'preprocessor': hp.choice('preprocessor', [1,2,3,4]), # (none, min_max, scaled, normalized)
        'C': hp.loguniform('C', np.log(10**(-10)), np.log(0.01)),
        'gamma': hp.loguniform('gamma', np.log(0.00001), np.log(10)),
	
        }


