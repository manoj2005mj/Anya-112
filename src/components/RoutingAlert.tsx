import { motion, AnimatePresence } from 'motion/react';
import { MapPin, Clock, Phone, X, AlertTriangle } from 'lucide-react';
import { FacilityInfo, RouteInfo } from '../lib/routing';

interface RoutingAlertProps {
  show: boolean;
  facility: FacilityInfo | null;
  route: RouteInfo | null;
  onClose: () => void;
}

export default function RoutingAlert({ show, facility, route, onClose }: RoutingAlertProps) {
  if (!facility || !route) return null;

  return (
    <AnimatePresence>
      {show && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.5 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black z-[2000]"
          />

          {/* Modal */}
          <div className="fixed inset-0 flex items-center justify-center z-[2001] p-4">
            <motion.div
              initial={{ opacity: 0, scale: 0.9, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.9, y: 20 }}
              className="bg-white rounded-2xl shadow-2xl max-w-md w-full overflow-hidden"
            >
              {/* Header with alert styling */}
              <div className="bg-gradient-to-r from-blue-600 to-blue-700 px-6 py-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-white/20 rounded-full flex items-center justify-center">
                      <AlertTriangle className="w-5 h-5 text-white" />
                    </div>
                    <div>
                      <h2 className="text-white font-bold text-lg">Help is on the way!</h2>
                      <p className="text-blue-100 text-sm">Emergency response dispatched</p>
                    </div>
                  </div>
                  <button
                    onClick={onClose}
                    className="text-white/80 hover:text-white transition-colors"
                  >
                    <X size={20} />
                  </button>
                </div>
              </div>

              {/* Content */}
              <div className="p-6 space-y-4">
                {/* Facility Info */}
                <div className="bg-blue-50 rounded-xl p-4 border border-blue-100">
                  <div className="flex items-start gap-3">
                    <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center flex-shrink-0">
                      <MapPin className="w-4 h-4 text-white" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs text-blue-600 font-semibold uppercase tracking-wider">
                        Responding Facility
                      </p>
                      <p className="text-gray-900 font-bold truncate">
                        {facility.name}
                      </p>
                      <p className="text-gray-500 text-sm truncate">
                        {facility.address}
                      </p>
                    </div>
                  </div>
                </div>

                {/* ETA Display */}
                <div className="bg-green-50 rounded-xl p-4 border border-green-100">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 bg-green-600 rounded-lg flex items-center justify-center flex-shrink-0">
                      <Clock className="w-4 h-4 text-white" />
                    </div>
                    <div>
                      <p className="text-xs text-green-600 font-semibold uppercase tracking-wider">
                        Estimated Arrival
                      </p>
                      <p className="text-gray-900 font-bold text-2xl">
                        {Math.round(route.duration_min)} min
                      </p>
                    </div>
                    <div className="ml-auto text-right">
                      <p className="text-xs text-green-600 font-semibold uppercase tracking-wider">
                        Distance
                      </p>
                      <p className="text-gray-700 font-semibold">
                        {route.distance_km} km
                      </p>
                    </div>
                  </div>
                </div>

                {/* Contact Info */}
                {facility.phone && (
                  <div className="bg-gray-50 rounded-xl p-4 border border-gray-200">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 bg-gray-600 rounded-lg flex items-center justify-center flex-shrink-0">
                        <Phone className="w-4 h-4 text-white" />
                      </div>
                      <div>
                        <p className="text-xs text-gray-500 font-semibold uppercase tracking-wider">
                          Emergency Contact
                        </p>
                        <p className="text-gray-900 font-bold">
                          {facility.phone}
                        </p>
                      </div>
                    </div>
                  </div>
                )}

                {/* Status Message */}
                <div className="text-center py-2">
                  <p className="text-gray-500 text-sm">
                    Please stay on the line and keep calm. Help is arriving.
                  </p>
                </div>
              </div>
            </motion.div>
          </div>
        </>
      )}
    </AnimatePresence>
  );
}
