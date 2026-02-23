import { motion } from 'motion/react';
import { Shield, Flame, Ambulance, Zap, Activity, AlertTriangle } from 'lucide-react';
import clsx from 'clsx';

interface DepartmentBadgesProps {
  departments: string[];
  severity: string | null;
}

const BADGE_CONFIG: Record<string, { icon: any, color: string, bg: string }> = {
  'Police': { icon: Shield, color: 'text-blue-400', bg: 'bg-blue-500/20' },
  'Fire': { icon: Flame, color: 'text-orange-400', bg: 'bg-orange-500/20' },
  'Ambulance': { icon: Ambulance, color: 'text-red-400', bg: 'bg-red-500/20' },
  'Electrical': { icon: Zap, color: 'text-yellow-400', bg: 'bg-yellow-500/20' },
  'Disaster Response': { icon: Activity, color: 'text-emerald-400', bg: 'bg-emerald-500/20' },
  'Default': { icon: AlertTriangle, color: 'text-gray-400', bg: 'bg-gray-500/20' }
};

export default function DepartmentBadges({ departments, severity }: DepartmentBadgesProps) {
  return (
    <div className="space-y-6">
      {/* Severity Indicator */}
      <div className="bg-zinc-900/50 rounded-xl p-4 border border-white/5">
        <h3 className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-3">Threat Level</h3>
        <div className="flex items-center gap-3">
          <div className={clsx(
            "h-3 w-full rounded-full overflow-hidden bg-zinc-800",
            "relative"
          )}>
            <motion.div 
              className={clsx(
                "absolute top-0 left-0 h-full transition-all duration-500",
                severity === 'Critical' ? 'bg-red-600' :
                severity === 'High' ? 'bg-orange-500' :
                severity === 'Medium' ? 'bg-yellow-500' :
                severity === 'Low' ? 'bg-blue-500' : 'bg-zinc-700'
              )}
              initial={{ width: '0%' }}
              animate={{ width: severity ? '100%' : '0%' }}
            />
          </div>
          <span className={clsx(
            "text-sm font-bold min-w-[60px] text-right",
            severity === 'Critical' ? 'text-red-500' :
            severity === 'High' ? 'text-orange-400' :
            severity === 'Medium' ? 'text-yellow-400' :
            severity === 'Low' ? 'text-blue-400' : 'text-zinc-600'
          )}>
            {severity || '---'}
          </span>
        </div>
      </div>

      {/* Departments Grid */}
      <div className="bg-zinc-900/50 rounded-xl p-4 border border-white/5">
        <h3 className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-3">Active Units</h3>
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
                    "flex items-center gap-3 p-3 rounded-lg border border-white/5",
                    config.bg
                  )}
                >
                  <Icon className={clsx("w-5 h-5", config.color)} />
                  <span className={clsx("text-sm font-medium", config.color)}>{dept}</span>
                </motion.div>
              );
            })
          ) : (
            <div className="col-span-2 text-center py-4 text-zinc-600 text-sm italic">
              No units dispatched yet
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
