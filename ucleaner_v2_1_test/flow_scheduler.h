// flow_scheduler.h — transcribed from Final Qwen.md Step 6
#pragma once
#include "ucleaner_types.h"
#include "prop_store.h"
#include "dep_graph.h"
#include <deque>
#include <unordered_set>
#include <unordered_map>
#include <functional>

namespace uc {

using FieldHandler = std::function<Status(FieldId, PropStore&)>;

class FlowScheduler {
public:
    static constexpr uint32_t DEFAULT_MAX_ITERATIONS = 64;

    void register_handler(FieldId field, FieldHandler handler) { handlers_[field] = handler; }
    void unregister_handler(FieldId field) { handlers_.erase(field); }
    void set_max_iterations(uint32_t n) { max_iterations_ = n; }

    Status enqueue(FieldId field) {
        if (field == FIELD_NULL) return Status::InvalidField;
        if (in_queue_.count(field)) return Status::Ok;
        work_queue_.push_back(field);
        in_queue_.insert(field);
        return Status::Ok;
    }

    Status run(PropStore& props, const DepGraph& deps) {
        iteration_count_ = 0;
        while (!work_queue_.empty()) {
            if (++iteration_count_ > max_iterations_) {
                work_queue_.clear(); in_queue_.clear();
                return Status::DepthExceeded;
            }
            FieldId field = work_queue_.front();
            work_queue_.pop_front();
            in_queue_.erase(field);
            auto it = handlers_.find(field);
            if (it != handlers_.end()) {
                Status s = it->second(field, props);
                if (s != Status::Ok) {
                    work_queue_.clear(); in_queue_.clear();
                    return s;
                }
            }
            const auto& dependents = deps.dependents_of(field);
            for (FieldId dep : dependents) {
                Status s = enqueue(dep);
                if (s != Status::Ok) { work_queue_.clear(); in_queue_.clear(); return s; }
            }
        }
        return Status::Ok;
    }

    bool is_empty() const { return work_queue_.empty(); }
    size_t queue_size() const { return work_queue_.size(); }
    uint32_t last_iteration_count() const { return iteration_count_; }
    void clear() { work_queue_.clear(); in_queue_.clear(); handlers_.clear(); }

private:
    std::deque<FieldId> work_queue_;
    std::unordered_set<FieldId> in_queue_;
    std::unordered_map<FieldId, FieldHandler> handlers_;
    uint32_t max_iterations_ = DEFAULT_MAX_ITERATIONS;
    uint32_t iteration_count_ = 0;
};

} // namespace uc
