import { Fragment } from "react";
import { View } from "react-native";
import styles from "../AppStyles";
import FlowStep from "./FlowStep";
import FlowConnector from "./FlowConnector";

export default function FlowRail({ steps = [], muted = false, compact = false }) {
  if (!steps.length) return null;

  return (
    <View style={[styles.flowRailWrap, compact && styles.flowRailWrapCompact]}>
      <View style={[styles.flowRail, compact && styles.flowRailCompact, muted && styles.flowRailMuted]}>
        {steps.map((step, index) => (
          <Fragment key={step.key}>
            <View style={styles.flowRailItem}>
              <FlowStep
                icon={step.icon}
                label={step.label}
                active={step.active}
                accessibilityLabel={step.a11y ? `${step.a11y}${step.active ? ", active" : ""}` : undefined}
              />
            </View>
            {index < steps.length - 1 ? (
              <FlowConnector active={step.active || steps[index + 1]?.active} />
            ) : null}
          </Fragment>
        ))}
      </View>
    </View>
  );
}
