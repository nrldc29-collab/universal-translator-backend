import { Text, StyleSheet } from "react-native";
import { LinearGradient } from "expo-linear-gradient";

interface GradientHeaderProps {
  title: string;
  subtitle?: string;
}

export default function GradientHeader({ title, subtitle }: GradientHeaderProps) {
  return (
    <LinearGradient
      colors={['#1e3a8a', '#0f172a']}
      start={{ x: 0, y: 0 }}
      end={{ x: 1, y: 1 }}
      style={styles.container}
    >
      <Text style={styles.title}>{title}</Text>
      {subtitle && <Text style={styles.subtitle}>{subtitle}</Text>}
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  container: {
    padding: 20,
    paddingTop: 40,
    borderBottomLeftRadius: 24,
    borderBottomRightRadius: 24,
    marginBottom: 20,
  },
  title: {
    fontSize: 32,
    fontWeight: "bold",
    color: '#fff',
    marginBottom: 4,
  },
  subtitle: {
    fontSize: 14,
    color: '#93a4bd',
  },
});