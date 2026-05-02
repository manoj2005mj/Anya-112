import { motion } from 'motion/react';
import { Shield, Flame, Ambulance, Zap, Activity, AlertTriangle } from 'lucide-react';
import clsx from 'clsx';

interface DepartmentBadgesProps {
  departments: string[];
  severity: string | null;
}

const SEVERITY_WIDTH: Record<string, string> = {
  Low: '25%',
  Medium: '50%',
  High: '75%',
  Critical: '100%',
};

const BADGE_CONFIG: Record<string, { icon: any, color: string, bg: string, border: string }> = {
  'Police': { icon: Shield, color: 'text-blue-700', bg: 'bg-blue-50', border: 'border-blue-100' },
  'Fire': { icon: Flame, color: 'text-orange-700', bg: 'bg-orange-50', border: 'border-orange-100' },
  'Ambulance': { icon: Ambulance, color: 'text-red-700', bg: 'bg-red-50', border: 'border-red-100' },
  'Electrical': { icon: Zap, color: 'text-yellow-700', bg: 'bg-yellow-50', border: 'border-yellow-100' },
  'Disaster Response': { icon: Activity, color: 'text-emerald-700', bg: 'bg-emerald-50', border: 'border-emerald-100' },
  'Default': { icon: AlertTriangle, color: 'text-zinc-600', bg: 'bg-zinc-50', border: 'border-zinc-100' }
};

export default function DepartmentBadges({ departments, severity }: DepartmentBadgesProps) {
  return (
    <div className="space-y-6">
      {/* Severity Indicator */}
      <div className="bg-white rounded-xl p-4 border border-zinc-200 shadow-sm">
        <h3 className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider mb-3">Threat Level</h3>
        <div className="flex items-center gap-3">
          <div className={clsx(
            "h-3 w-full rounded-full overflow-hidden bg-zinc-100",
            "relative"
          )}>
            <motion.div
              className={clsx(
                "absolute top-0 left-0 h-full transition-all duration-500 shadow-sm",
                severity === 'Critical' ? 'bg-red-600' :
                  severity === 'High' ? 'bg-orange-500' :
                    severity === 'Medium' ? 'bg-yellow-500' :
                      severity === 'Low' ? 'bg-blue-500' : 'bg-transparent'
              )}
              initial={{ width: '0%' }}
              animate={{ width: severity ? (SEVERITY_WIDTH[severity] || '0%') : '0%' }}
            />
          </div>
          <span className={clsx(
            "text-sm font-black min-w-[60px] text-right",
            severity === 'Critical' ? 'text-red-600' :
              severity === 'High' ? 'text-orange-600' :
                severity === 'Medium' ? 'text-yellow-600' :
                  severity === 'Low' ? 'text-blue-600' : 'text-zinc-300'
          )}>
            {severity || 'NORMAL'}
          </span>
        </div>
      </div>

      {/* Departments Grid */}
      <div className="bg-white rounded-xl p-4 border border-zinc-200 shadow-sm">
        <h3 className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider mb-3">Active Units</h3>
        <div className="grid grid-cols-2 gap-3">
          {departments.length > 0 ? (
            departments.map((dept) => {
              const config = BADGE_CONFIG[dept] || BADGE_CONFIG['Default'];
              const Icon = config.icon;
              return (
                <motion.div
                  key={dept}
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className={clsx(
                    "flex items-center gap-3 p-3 rounded-lg border shadow-sm",
                    config.bg,
                    config.border
                  )}
                >
                  <Icon className={clsx("w-5 h-5", config.color)} />
                  <span className={clsx("text-sm font-bold", config.color)}>{dept}</span>
                </motion.div>
              );
            })
          ) : (
            <div className="col-span-2 text-center py-4 text-zinc-400 text-xs italic">
              No units dispatched yet
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
