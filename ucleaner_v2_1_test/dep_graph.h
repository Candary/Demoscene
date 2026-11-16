// dep_graph.h — transcribed from Final Qwen.md Step 4
// FIX: added #include <algorithm> for std::remove_if
#pragma once
#include "ucleaner_types.h"
#include <vector>
#include <unordered_map>
#include <unordered_set>
#include <algorithm>

namespace uc {

struct DepEdge { FieldId src; FieldId dst; };

class DepGraph {
public:
    Status add_dependency(FieldId src, FieldId dst) {
        if (src == FIELD_NULL || dst == FIELD_NULL) return Status::InvalidField;
        if (src == dst) return Status::SelfReference;
        auto it = forward_.find(src);
        if (it != forward_.end()) {
            for (FieldId e : it->second) if (e == dst) return Status::Ok;
        }
        forward_[src].push_back(dst);
        reverse_[dst].push_back(src);
        edges_.push_back({src, dst});
        return Status::Ok;
    }

    const std::vector<FieldId>& dependents_of(FieldId src) const {
        static const std::vector<FieldId> empty;
        auto it = forward_.find(src);
        return it != forward_.end() ? it->second : empty;
    }
    const std::vector<FieldId>& dependencies_of(FieldId dst) const {
        static const std::vector<FieldId> empty;
        auto it = reverse_.find(dst);
        return it != reverse_.end() ? it->second : empty;
    }

    void remove_entity_dependencies(EntityId entity) {
        edges_.erase(
            std::remove_if(edges_.begin(), edges_.end(),
                [entity](const DepEdge& e) {
                    return field_entity(e.src) == entity || field_entity(e.dst) == entity;
                }),
            edges_.end());
        forward_.clear(); reverse_.clear();
        for (const auto& e : edges_) {
            forward_[e.src].push_back(e.dst);
            reverse_[e.dst].push_back(e.src);
        }
    }

    bool has_cycle() const {
        std::unordered_map<FieldId, uint8_t> color;
        for (const auto& e : edges_) { color[e.src] = 0; color[e.dst] = 0; }
        for (const auto& p : color) {
            if (p.second == 0) { if (dfs_visit(p.first, color)) return true; }
        }
        return false;
    }

    size_t edge_count() const { return edges_.size(); }
    void clear() { edges_.clear(); forward_.clear(); reverse_.clear(); }

private:
    bool dfs_visit(FieldId node, std::unordered_map<FieldId, uint8_t>& color) const {
        color[node] = 1;
        auto it = forward_.find(node);
        if (it != forward_.end()) {
            for (FieldId nb : it->second) {
                auto cit = color.find(nb);
                if (cit == color.end()) continue;
                if (cit->second == 1) return true;
                if (cit->second == 0) { if (dfs_visit(nb, color)) return true; }
            }
        }
        color[node] = 2;
        return false;
    }

    std::vector<DepEdge> edges_;
    std::unordered_map<FieldId, std::vector<FieldId>> forward_;
    std::unordered_map<FieldId, std::vector<FieldId>> reverse_;
};

} // namespace uc
